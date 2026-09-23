# Basis-Stückliste – Entscheidungen

Stand: 2026-09-23. Referenz für `EXPORT-PLAN.md` und `AGENT-PLAN.md`. Jede Regel steht nur hier; die Pläne verweisen per Nummer (D1, D2, …).

## Ziel

Aus konfigurierbaren SAP-Stücklisten (Werk 4000, Verwendung 1) die **Basis-Version** ableiten: die Stückliste, die entsteht, wenn jedes Merkmal seinen fachlich festgelegten Basiswert hat. Ergebnis dient als ML-Trainingsgrundlage. So weit von SAP entfernt wie möglich, so nah wie nötig: kein CU50-Abgleich, alle Logik läuft auf exportierten Tabellen in Postgres.

## Regelwerk

- **D1 Rangliste pro Merkmal.** Basis wird fachlich pro Merkmal als *geordnete Liste* von Werten festgelegt (Rang 1 stärkster). Jeder Wert hat einen Status: `BASIS` (mit Rang), `NICHT_BASIS`, `OFFEN` (noch nicht entschieden). Werte kommen vom Fachbereich, bleiben änderbar.
- **D2 Entscheidung pro Ebene.** Für jede Stückliste (STLNR) unabhängig: pro Merkmal alle Werte sammeln, die in den Bedingungen dieser Stückliste vorkommen; der vorkommende Wert mit bestem Rang gewinnt. Kein Blick nach oben oder unten im Baum.
- **D3 SITZHOEHE** ist D2 mit numerischem Rang: niedrigster vorkommender Wert gewinnt.
- **D4 Kein Rangwert vorhanden.** Kommen zu einem Merkmal nur `NICHT_BASIS`/`OFFEN`-Werte vor: Stückliste erhält Marker `kein_rang_fuer:<MERKMAL>`, betroffene Positionen → `manuell_prüfen`.
- **D5 Multi-Werte** (`BS/FK`, `FK+BS`): passen, wenn der gewählte Wert enthalten ist. Enthält der Ausdruck einen unbekannten Wert → zusätzlich `manuell_prüfen`.
- **D6 Alias-Tabelle.** Merkmalkürzel in Bedingungsnamen (`SQ`, `SIQUALI`, `RUCK`, `E`, `F` …) → kanonischer Name = `CABN.ATNAM`. Liegt in der DB. Unbekanntes Kürzel → `manuell_prüfen`. `OPTIK`/`ARM` ohne Suffix werden nicht geraten → `manuell_prüfen`.
- **D7 Systemregeln** (`PP4000_KS_VERERBEN`, `FUNK_RUECK_ZE`, rein numerische Namen …) sind Pseudo-Merkmale in derselben Regeltabelle: Merkmal = Beziehungsname, Wert = `vorhanden`, Status wie D1. Keine Präfix-Heuristik im Code. Neue Namen landen automatisch als `OFFEN`.
- **D8 Drei Zustände überall.** Merkmalswerte, Aliasse und Systemregeln haben `BASIS`/`NICHT_BASIS`/`OFFEN`. `OFFEN` und Unbekanntes führen zu `manuell_prüfen`, nie zu stillem Einschluss oder Ausschluss.

## Bewertung einer Position

- **D9 UND-Logik.** Alle Auswahlbedingungen an einer Position (alle `KNNUM` zum `KNOBJ`) müssen passen. Eine nicht passende → `ausgeschlossen`.
- **D10 Nur Auswahlbedingungen selektieren.** `CUKB.KNART` entscheidet. Prozeduren werden ignoriert, aber pro Position mit Status `prozedur_ignoriert` gezählt und im Report ausgewiesen. Prototyp ohne `KNART`: alle Beziehungen gelten als Auswahlbedingungen, Lauf-Marker `knart_fehlt`; im Review darauf hinweisen.
- **D11 Nicht parsbare Bedingungsnamen** → `manuell_prüfen` mit Grund, Liste für den Menschen. Niemals `unbedingt`.
- **D12 Pfadvererbung.** `ausgeschlossen` vererbt sich auf alle Kindpositionen (Status `ausgeschlossen_vererbt`). Unter `manuell_prüfen` wird weiter aufgelöst, Kinder erhalten `unterhalb_manuell`.
- **D13 Positionstypen.** `L`, `N` → Export und Auflösung. `K` (Klassenposition) → `manuell_prüfen`. `D`, `T` → ignoriert.
- **D14 Gültigkeit.** Stichtag = Exportdatum. `LKENZ` gesetzt oder `DATUV` > Stichtag → Zeile existiert nicht. Gilt für STPO, STAS, STKO, CUOB, CUKB. Bei mehreren CUKB-Zeilen pro `KNNUM` (Versionszähler `ADZHL`): die gültige mit größtem `DATUV` ≤ Stichtag und `KNSTA` = freigegeben.
- **D15 Eine Stückliste pro Material.** Mehr als ein `STLNR` (Werk 4000, Verwendung 1) pro `MATNR` ist ein Datenfehler → Report, Material nicht aufgelöst.

## Ausgabe

- **D16 Eine Zeile pro Vorkommen.** Komponente unter zwei Baugruppen = zwei Zeilen. Keine Summierung im Kern; Summen sind Views.
- **D17 Kumulierte Menge** = Produkt der `MENGE` entlang des Pfades, jede Stufe geteilt durch `STKO.BMENG` der Stückliste.
- **D18 Entscheidungsspur pro Position:** Beziehungsnamen, geparste (Merkmal, Wert)-Paare, gewählter Rangwert pro Merkmal auf dieser Ebene, Status, Grund, Regelversion. Ausgeschlossene Positionen bleiben im Ergebnis sichtbar.
- **D19 SAP-Format-Export** (fest, nicht ändern): `Werk | Material | ObjektId | Materialkurztext DE | Menge | ME | PTp | Disp. | Warengrp` (+ `MArt`, `SoB` sofern MARA/MARC exportiert). Erste Zeile pro Root-Material = Kopfzeile ohne ObjektId/Menge. Enthält nur Positionen mit Status `basis`, `unbedingt`.

## Daten und Betrieb

- **D20 Postgres.** SAP-Tabellen werden nächtlich in ein Exportschema geladen (lesend). Alles Eigene in Schema `basis_bom`. Kein dbt; SQL-Views als Dateien im Repo.
- **D21 Historie.** Regel-, Alias-, Systemregel-Tabellen tragen `gueltig_von`, `gueltig_bis`, `geaendert_von`. Jeder Lauf speichert `lauf_id`, `regel_version` (Zeitstempel des Regelstands), `export_datum`.
- **D22 Root-Materialien** = Materialliste des Bereichs STO-MON, Werk 4000, aus der Planzeiten-Tabelle (`Kopie von 4000_STO_OKU_Alle Modelle_Planzeiten_Merkmal.xlsx`), gepflegt als Tabelle `root_material` in `basis_bom`, minus `root_ausschluss`. Die Stammdatenregel (MARA `KZKFG = X` ∧ MAST `WERKS = 4000` ∧ `STLAN = 1`) ist **Prüfung**, nicht Quelle: jedes Root-Material muss sie erfüllen, sonst Report. Die hartcodierte `MATERIAL_LIST` im Legacy-Skript stammt aus derselben Datei und dient als Abgleich beim ersten Laden.
- **D23 Lauf.** Reihenfolge: Konsistenzprüfungen → Auflösung → Regression gegen bestätigte Reviews → SAP-Format-Export. Prototyp: manuell aus dem Devcontainer, Regression meldet nur. Prod (später, eigenes Blatt): Trigger durch Node-RED nach dem nächtlichen Export, Regression blockiert den Export.
- **D24 Review.** Fachbereich beurteilt das Ergebnis pro Position: `richtig` / `fehlt` / `gehoert_nicht_rein` + Kommentar. Prototyp: Review-Blatt (XLSX) pro Material, ausgefüllt zurück und in Tabelle `review` importiert. Offene Fälle als View/CSV, kein Browser-Tool. Regeln wachsen Beispiel für Beispiel.

## Offene Fakten (in den Daten klären, nicht entscheiden)

- F1 Mehrfachzeilen in CUKB pro `KNNUM` – Ursache `ADZHL`/`AENNR`?
- F2 Negationen in Bedingungsnamen (`<>`, `NICHT`, `!=`)?
- F3 Belegung von `STPO.ALPGR`/`ALPRF` (Alternativpositionen)?
- F4 Verteilung `CUKB.KNART` an STPO-Positionen (Anteil Prozeduren)?
- F5 Anzahl Materialien mit >1 `STLNR` (D15-Verstöße)?
- F6 Anteil Stücklisten mit `STKO.BMENG ≠ 1`?

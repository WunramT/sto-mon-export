# Fragen an den Menschen

Gesammelt beim Umsetzen von `docs/AGENT-PLAN.md`. Jede Stelle, an der `DECISIONS.md` keine eindeutige Antwort
gibt, steht hier mit der Annahme, mit der der Prototyp bis zur Antwort läuft. Nummern `Qn` bleiben stabil.

## Noch nicht mit echten Daten gelaufen

Die Umgebung, in der der Prototyp gebaut wurde, hatte keinen Zugriff auf `/data/exports`. Alles ist gegen die
synthetischen Fixtures (`tests/fixtures/`) gebaut und getestet. Offen, bis jemand im Devcontainer
`basis-bom db init --from-dir /data/exports` ausführt:

- Prüfpunkte 1–8 aus `docs/EXPORTE.md` – der Loader beantwortet sie automatisch und schreibt sie unten in den
  generierten Abschnitt dieser Datei.
- F1–F6 als Zahlen – `notebooks/00_exploration_fakten.py` gegen die geladenen Daten ausführen.
- Laufzeitziel „unter 15 Minuten“ für `db init --from-dir` und „unter fünf Minuten“ für `run --matnr …`.
- Die beschreibenden Header in `basis_bom/headers.py` sind bis auf die drei aus dem Legacy-Skript belegten
  (`ZUORDNUNGSNUMMER`, `INTERNE NUMMER DES WISSENSBAUSTEINS`, `BEZIEHUNG`) aus SAP-Feldbezeichnern abgeleitet
  (`# vermutet`). Unbekannte Spalten meldet der Loader; bitte ins Mapping übernehmen.

## Gerüst und Laden (Phase 1–2)

- **Q1 Repo-Name.** Der Plan spricht von `ML_Server`, das Repo heißt `sto-mon-export`. `workspaceFolder` ist wie
  im Plan `/workspaces/ML_Server` (nur ein Pfad im Container). Umbenennen?
- **Q2 `openpyxl`** ist zusätzlich Laufzeitabhängigkeit (XLSX lesen, Review-Blätter schreiben).
- **Q3 `notebooks/legacy_export_worker.ipynb`.** `docs/EXPORTE.md` verlangt, `export_worker.ipynb` ins Repo zu
  übernehmen – die Datei liegt nicht im Repo und war hier nicht erreichbar. Bitte nachreichen.
- **Q4 D14 bei mehreren Versionen (STPO/STAS/STKO/CUOB/CUKB).** D14 regelt Versionen nur für CUKB („größtes
  DATUV ≤ Stichtag“). Umgesetzt für alle versionierten Tabellen einheitlich: pro Schlüssel die neueste Version mit
  `DATUV` ≤ Stichtag (Zähler `STPOZ`/`STASZ`/`STKOZ`/`ADZHL` als Tiebreak); ist *diese* gelöscht (`LKENZ`/`LOEKZ`),
  existiert das Objekt nicht. Die wörtliche Lesart („gelöschte Zeilen weg, dann neueste“) würde eine ältere Version
  wiederbeleben, wenn die neueste eine Löschung ist (typisch bei STAS). Passt die Lesart?
- **Q5 MAST und D14.** D14 nennt MAST nicht. Umgesetzt: MAST-Zeilen mit `LKENZ` zählen nicht zu S
  (EXPORT-PLAN Phase 1), `DATUV` > Stichtag ebenfalls nicht – sonst erzeugen gelöschte Zuordnungen falsche
  D15-Verstöße.
- **Q6 SAP-Domänen.** Angenommen: `CUKB.KNSTA = 1` freigegeben; `CUKB.KNART = 5` Auswahlbedingung, `7` Prozedur.
  Andere `KNART`-Werte (Vorbedingung, Constraint …) → `manuell_prüfen`. Bitte bestätigen (F4 zeigt die
  tatsächliche Verteilung).
- **Q7 Mengen mit Punkt.** `1,5` und `1.000,5` werden als Dezimalkomma gelesen; `1.000` ohne Komma als 1,0
  (englisches Format). Falls die STPO-CSV Tausenderpunkte ohne Nachkommastellen enthält, bitte melden.
- **Q8 STAS.** Hat eine Stückliste STAS-Einträge, gelten nur die Knoten, deren neueste STAS-Version für die
  Alternative gültig ist. Stücklisten ganz ohne STAS-Einträge verwenden alle gültigen STPO-Positionen.

## Schema und Seeds (Phase 3)

- **Q9 Bedeutung des Alias-Status.** D8 verlangt drei Zustände auch für Aliasse. Umgesetzt: `BASIS` = Zuordnung
  bestätigt, `OFFEN`/`NICHT_BASIS` = nicht verwendbar → `manuell_prüfen`. `OPTIK` und `ARM` sind als `OFFEN`
  ohne Merkmal geseedet (D6: nicht raten). Unbekannte Kürzel landen automatisch als `OFFEN`.
- **Q10 Geratene Ränge aus der Set-Reihenfolge.** Python-Sets haben keine Ordnung; der Rang folgt der
  Reihenfolge im Quelltext von `MANUAL_DEFAULTS`. Bitte je Merkmal bestätigen oder umsortieren:
  - `FUNKTION`: 1 `X`, 2 `MANUEL`, 3 `BK` (offen: `WA1`, `VZMO`)
  - `RUECKEN_FUNK`: 1 `X`, 2 `ST` (offen: `KV`)
  - `ELEKTRO`: 1 `X` (offen: `FA`); `AKKU`: 1 `X`; `ARM_L`/`ARM_R`: 1 `X` (offen: `LAL`)
  - `RUECKEN_OPTIK` 1 `A`, `ARM_OPTIK` 1 `1`, `SITZQUALI` 1 `HR` stammen aus `DEFAULT_PROFILE` (eindeutig).
  - `MOTOR`, `GASDRUCK`, `FUSS`, `3_FUSS`, `SITZTIEFE`: im Legacy-Skript ohne Default → keine Seeds; jede
    Bedingung auf diese Merkmale führt zu `kein_rang_fuer:<M>` bis der Fachbereich Ränge setzt.
- **Q11 Systemregeln nicht geseedet.** Das Legacy-Skript hat `PP4000_…`, `PP_…`, `WERK_…`, `FUNK_RUECK_ZE` und
  rein numerische Namen per Präfix-Heuristik *eingeschlossen*. D7 verbietet die Heuristik; diese Namen landen
  jetzt beim ersten Lauf als `OFFEN` (Merkmal = Name, Wert `vorhanden`) und führen bis zur Entscheidung zu
  `manuell_prüfen`. Sollen die bekannten Systemregeln vorab als `BASIS` gesetzt werden?
- **Q12 Zusätzliche Spalten.** `review.menge` (Vergleichsgröße der Regression, D23), `review.lauf_id`,
  `aufloesung.lfd/posnr/pfad` (Reihenfolge, Pfad für D16) und `basis_bom.ladeprotokoll` sind über den Plan hinaus
  angelegt.

## Parser (Phase 4)

- **Q13 `ELEKTRO=FAL_SH48_SQ=HR`.** Das Legacy-Skript liefert `ELEKTRO='FAL_SH48'`. Der neue Parser liest
  `SH48` als Sitzhöhe 48 → `ELEKTRO=FAL`, `SITZHOEHE=48`, `SITZQUALI=HR`. Richtig so?
- **Q14 Zweistellige Zahl = SITZHOEHE.** Aus dem Legacy-Skript übernommen (`…_2_45` → `SITZHOEHE=45`), ebenso
  `SH48`/`SITZH46` (Sitzhöhen-Alias direkt mit Ziffern). Das ist eine Heuristik im Code; soll sie bleiben?
- **Q15 Negation (F2).** Bis F2 geklärt ist, sind Namen mit `<>`, `!=`, `NICHT`, `NOT` nicht parsbar →
  `manuell_prüfen`. Notebook 00 listet die betroffenen Namen.
- **Q16 Systemregel-Kandidat.** „Ein Name ohne einziges `=`“ (nach Normalisierung von `ALIAS WERT` zu
  `ALIAS=WERT`) ist Systemregel-Kandidat. Damit wird auch ein alleinstehendes `SITZQ_HR` (ohne `=`) zu einem
  Pseudo-Merkmal `SITZQ_HR` = `vorhanden` statt zu `SITZQUALI=HR`. Namen mit Leerzeichen, die nicht die Form
  `ALIAS WERT` haben, sind nicht parsbar.

## Ranking (Phase 5)

- **Q17 OFFEN-Wert neben gewähltem Rangwert.** Beispiel: Ebene mit `SQ=HR` (BASIS, Rang 1) und `SQ=FK`
  (OFFEN). D2/D4 sagen: HR gewinnt, die FK-Position passt nicht → `ausgeschlossen`. D8 sagt: OFFEN führt nie zu
  stillem Ausschluss. Umgesetzt: `ausgeschlossen`, aber sichtbar – Grund nennt den OFFEN-Wert, die Stückliste
  trägt den Marker `offen_neben_rang:SITZQUALI` (View `offene_faelle`). Soll stattdessen `manuell_prüfen` gelten?
  Das würde mit dem Übergang `cawn_fehlt` (alle beobachteten Werte OFFEN) fast jede Variantenposition manuell
  machen.
- **Q18 Multi-Wert mit unbekanntem Teil (D5)** führt nur dann zu `manuell_prüfen`, wenn der gewählte Wert
  enthalten ist (`HR/XX` bei HR). Passt der Ausdruck ohnehin nicht (`BS/XX` bei HR), bleibt es `ausgeschlossen`
  mit Hinweis im Grund. „Unbekannt“ heißt: nicht in der Regeltabelle oder Status OFFEN.
- **Q19 SITZHOEHE (D3).** Nur Zahlenwerte konkurrieren; `NICHT_BASIS`-Werte sind ausgenommen, nicht-numerische
  Werte führen zu `kein_rang_fuer:SITZHOEHE`.
- **Q20 Systemregel mit NICHT_BASIS.** Ein Pseudo-Merkmal hat nur den Wert `vorhanden`. Wird er `NICHT_BASIS`
  gesetzt, greift D4 wörtlich (`kein_rang_fuer` → `manuell_prüfen`), nicht `ausgeschlossen`. Gewünscht?

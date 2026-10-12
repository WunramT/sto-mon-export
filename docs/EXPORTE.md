# Vorhandene Exporte (Dev-Daten)

Ablage außerhalb des Repos: `C:\Users\wunram\codebase\mlp_refa_sto_mon_export\export`, im Devcontainer als `/data/exports` gemountet. Der Loader (`basis-bom db init --from-dir /data/exports`) liest **nur** die Dateien in der Spalte „maßgeblich"; alles andere ignoriert er. Stand: 2026-09-23.

## Maßgebliche Dateien

| Tabelle | Datei | Format | Header | Stichtag | Größe | Filter (EXPORT-PLAN) |
|---|---|---|---|---|---|---|
| MAST | `EXPORT_mast_20260923_150612.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 15 MB | WERKS 4000, STLAN 1 |
| STPO | `fa_stpo_202606291123.csv` | CSV `;` | technisch, mit POSTP | 2026-06-29 | 1,04 GB | **ungefiltert** – Loader filtert chunkweise auf `STLNR ∈ S` |
| STAS | `EXPORT_stas_20260923_142938.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 3,4 MB | STLNR ∈ S |
| STKO | `EXPORT_stko_20260923_144510.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 1,3 MB | STLNR ∈ S |
| CUOB | `EXPORT_20260512_153230_cuob.XLSX` | XLSX | beschreibend | 2026-05-12 | 780 KB | aktuell laut TW |
| CUKB | `EXPORT_20260512_153418_CUKB.XLSX` | XLSX | beschreibend | 2026-05-12 | 40 KB | aktuell laut TW – `KNART` prüfen (Prüfpunkt 1) |
| CUKBT | `EXPORT_CUKBT_20260923_150301.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 18 KB | KNNUM ∈ W |
| CUKN | `EXPORT_CUKN_20261012_085449.xlsx` | XLSX | beschreibend (belegt) | 2026-10-12 | – | KNNUM ∈ W; **optional** – Quelltext des Beziehungswissens (unten) |
| MARA | `EXPORT_mara_20260923_145220.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 15 MB | MATNR ∈ M |
| MARC | `EXPORT_marc_20260923_141650.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 15 MB | WERKS 4000 |
| MAKT | `EXPORT_makt_20260923_144656.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 500 KB | MATNR ∈ M, SPRAS D |
| CABN | `EXPORT_cabn_20260923_142303.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 520 KB | prüfen: 520 KB ist viel für ~15 Merkmale, evtl. ungefiltert |
| root_material (D22) | `Kopie von 4000_STO_OKU_Alle Modelle_Planzeiten_Merkmal.xlsx` | XLSX | fachlich | — | 145 KB | — |

„Header beschreibend (vermutl.)": SE16-Exports tragen Feldbezeichner statt technischer Namen; der Loader mappt beides (`basis_bom/headers.py`). Beim ersten Laden die tatsächlichen Header pro Datei ins Mapping aufnehmen.

Stichtage sind gemischt (Mai/Juni/September). Für Dev-Daten erlaubt: `export_datum` pro Tabelle aus dem Dateinamen, Lauf-Stichtag = jüngstes Datum, Warnung. Im Prod (nächtlicher Export) gilt D14 strikt: abweichende Daten → Fehler.

## CUKN – Quelltext des Beziehungswissens

Merkmale und Werte einer Auswahlbedingung liest der Prototyp aus dem **Quelltext** (CUKN), nicht aus dem Namen
`CUKB.KNNAM` (ungenau, z. B. Name `RUECKEN_FUNK=X,FUNKTION=X`, Text
`$parent.W_RUECKENVERST ='X' and $parent.W_FUNKTION = 'X'.`). Fehlt CUKN oder ein Baustein darin, wird wie bisher
der Name gelesen (Marker `cukn_fehlt`, Hinweis in der Oberfläche „aus dem Namen gelesen“). Dateiname wird ohne
Rücksicht auf Groß-/Kleinschreibung gesucht (`.xlsx`).

| Header (SE16) | technisch | Inhalt |
|---|---|---|
| Interne Nummer des Wissensbausteins | `KNNUM` | Schlüssel |
| int. Zähler | `ADZHL` | Version (wie CUKB) |
| Blockzähler Wissensbaustein | `BLKNR` (Name angenommen) | mehrere Zeilen je Baustein → nach Blockzähler aneinanderhängen |
| Löschkennzeichen / Änderungsnummer / Gültig ab | `LKENZ` / `AENNR` / `DATUV` | D14 |
| Gültig bis | `DATUB` (Name angenommen) | nicht ausgewertet |
| BIN2-Datenelement fuer SYST | `LAENGE` (Name angenommen) | benutzte Länge des Blocks |
| Datenblock für Wissensablage | `KNBLK` | Text |

Format des Datenblocks (aus den Daten belegt): 6-stellige Zeilenanzahl, dann Zeilen zu 72 Zeichen (mit Leerzeichen
aufgefüllt), Länge = 6 + 72·n. Kommentarzeilen beginnen mit `*`. Dekodieren: `basis_bom/bedingung.py`
(`dekodiere`, `text_aus_bloecken`; die Länge stellt am Blockende abgeschnittene Leerzeichen wieder her).
Version (D14): je KNNUM die von CUKB gewählte Version (`ADZHL`), sonst die neueste CUKN-Version mit
`DATUV` ≤ Stichtag; ist sie gelöscht, hat der Baustein keinen Text. Stand 12.10.2026: 130 Bausteine, je eine Zeile
(Blockzähler 0, ADZHL 0, ohne Löschkennzeichen) – deckt alle 130 verschiedenen KNNUM aus W ab.

Nach dem ersten Laden mit CUKN: `basis-bom regel umschluesseln` (Vorschau) und `--ausfuehren` – die Regeln hängen
bisher an Legacy-Merkmalen (`FUNKTION`), der Text liefert die SAP-Merkmale (`W_FUNKTION`), docs/FRAGEN.md Q52.

## Schlüsselmengen (manuell erzeugt, nur Abgleich)

`S.csv` (STLNR), `P_idnrk.csv` (IDNRK aus P), `M.csv` (MATNR), `W.csv` (KNNUM) – erzeugt mit `export_worker.ipynb`. Der Loader berechnet S/P/M/W selbst aus den geladenen Tabellen und vergleicht gegen diese Dateien; Differenzen ins Protokoll. `export_worker.ipynb` als `notebooks/legacy_export_worker.ipynb` ins Repo übernehmen (Referenz, nicht ausführen).

## Nicht verwenden (überholt)

- `st_mast_202605111439.csv`, `fa_mara_202606291607.csv`, `fa_marc_202606291607.csv` – Volltabellen, ersetzt durch die gefilterten XLSX vom 23.09.

## Fehlt weiterhin

- **CAWN, CAWNT** – Merkmals*werte*. CABN allein liefert nur Namen (reicht für die Alias-Tabelle, D6), nicht die Werteliste für die Rangtabelle (D1). Bis dahin Übergangsregel: Rangliste aus beobachteten Werten, Marker `cawn_fehlt`.
- **STPO gefiltert** – für Dev löst der Loader das per Chunk-Filter; für Prod ist es der wichtigste Hebel des Export-Teams.

## Zu prüfen beim ersten Laden (Ergebnis in `docs/FRAGEN.md`)

1. CUKB-XLSX: Spalte für `KNART` („Art des Beziehungswissens"), `KNSTA`, `DATUV`, `ADZHL` vorhanden? Fehlt `KNART` → Prototyp läuft mit Marker `knart_fehlt` (D10), Ergebnis in `FRAGEN.md`.
2. CUOB/CUKB: bereits auf Werk 4000 gefiltert? Vergleich der KNNUM-Menge mit `W.csv`.
3. MAST/STPO/STAS/STKO: Spalten `LKENZ`, `DATUV`, `AENNR` vorhanden? Sonst D14 auf Dev-Daten nicht prüfbar.
4. STPO: Zeilen roh vs. nach `STLNR ∈ S` – die Zahl für EXPORT-PLAN Phase 0.
5. Planzeiten-XLSX: Spalte mit Materialnummer, Blätter, Duplikate, Materialien ohne Stückliste; Abgleich gegen `MATERIAL_LIST` aus `legacy/basis_bom_v0.py` in beide Richtungen.
6. CABN: Anzahl Zeilen und ob `ATNAM` alle kanonischen Merkmale der Alias-Tabelle enthält; ist die Datei ungefiltert, nur diese Zeilen laden.
7. Materialnummern in den XLSX: als Text mit führenden Nullen oder als Zahl? Nur dokumentieren, der Loader normalisiert.
8. Kein XLSX-Blatt hat genau 1.048.576 Zeilen (Excel-Grenze, stilles Abschneiden).
11. CUKN: Wie viele Auswahlbedingungen (KNNUM in CUKB) haben Quelltext, wie viele werden aus dem Namen gelesen
    (generierter Prüfpunkt 11; erwartet auf den Dev-Daten: alle).

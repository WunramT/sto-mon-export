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
| MARA | `EXPORT_mara_20260923_145220.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 15 MB | MATNR ∈ M |
| MARC | `EXPORT_marc_20260923_141650.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 15 MB | WERKS 4000 |
| MAKT | `EXPORT_makt_20260923_144656.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 500 KB | MATNR ∈ M, SPRAS D |
| CABN | `EXPORT_cabn_20260923_142303.XLSX` | XLSX | beschreibend (vermutl.) | 2026-09-23 | 520 KB | prüfen: 520 KB ist viel für ~15 Merkmale, evtl. ungefiltert |
| root_material (D22) | `Kopie von 4000_STO_OKU_Alle Modelle_Planzeiten_Merkmal.xlsx` | XLSX | fachlich | — | 145 KB | — |

„Header beschreibend (vermutl.)": SE16-Exports tragen Feldbezeichner statt technischer Namen; der Loader mappt beides (`basis_bom/headers.py`). Beim ersten Laden die tatsächlichen Header pro Datei ins Mapping aufnehmen.

Stichtage sind gemischt (Mai/Juni/September). Für Dev-Daten erlaubt: `export_datum` pro Tabelle aus dem Dateinamen, Lauf-Stichtag = jüngstes Datum, Warnung. Im Prod (nächtlicher Export) gilt D14 strikt: abweichende Daten → Fehler.

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

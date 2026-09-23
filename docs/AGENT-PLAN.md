# Agenten-Plan: Basis-Stückliste

Du baust im Repo `ML_Server` das Paket `basis_bom`, das aus SAP-Exporttabellen in Postgres die Basis-Stückliste ableitet. Arbeite die Phasen in Reihenfolge ab; jede endet mit einem prüfbaren Kriterium. Vor Phase 1 nichts implementieren.

## Umfang: Prototyp

Ziel dieses Durchlaufs ist ein **Prototyp**, mit dem die Fachabteilung prüft, ob der Weg trägt. Kein Prod-Betrieb. Konkret:
- Datenquelle sind die manuellen Exporte in `/data/exports` (siehe `docs/EXPORTE.md`); gemischte Stichtage sind erlaubt.
- Phasen 1–7 und 9 gehören zum Prototyp. Phase 8 nur als CLI (`run`, `check`, `export`, `review-export`); kein `serve`, kein Betriebs-Dockerfile, keine Node-RED-Anbindung.
- Regression (Phase 7) wird gebaut, aber blockiert nichts, solange `bestaetigt` leer ist.
- Fehlt eine Tabelle oder Spalte, gilt die Ersatzregel aus `docs/EXPORT-PLAN.md` „Übergang" mit sichtbarem Marker – der Prototyp läuft weiter, die Lücke steht im Report. Fehlt `CUKB.KNART`, werden alle Beziehungen als Auswahlbedingungen behandelt (Verhalten des Legacy-Skripts) und der Lauf trägt den Marker `knart_fehlt`.
- Das Ergebnis für die Fachabteilung ist pro Material: SAP-Format-Export (D19), ein Review-Blatt (Phase 7) und das Debug-Notebook (Phase 9). Alles, was der Mensch sieht, kommt aus diesen drei Dingen.

## Pflichtlektüre

- `docs/DECISIONS.md` – alle fachlichen Regeln (D1–D24) und offenen Fakten (F1–F6). Jede Implementierungsentscheidung verweist auf eine D-Nummer; findest du keine, ist es eine Frage an den Menschen, kein Ratespiel.
- `docs/EXPORT-PLAN.md` – Tabellen, Spalten, Ersatzregeln bis Exporte da sind.
- `docs/EXPORTE.md` – welche der vorhandenen Dateien für welche Tabelle maßgeblich ist, Header-Stil, Stichtage, Lücken.
- `legacy/basis_bom_v0.py` – der bisherige Prototyp. Quelle für Parser-Testfälle, Spaltennamen der bestehenden Exporte und das Zielformat. Sein Verhalten ist an mehreren Stellen bewusst überholt (ODER statt UND, keine Pfadvererbung, unparsbar = unbedingt, Präfix-Heuristik) – übernimm Struktur und Testfälle, nicht die Logik.

## Arbeitsweise

- **Notebook-first.** Jedes Modul entsteht neben einem Notebook in `notebooks/`, das es benutzt und zeigt. Notebooks sind jupytext-gepaarte `.py` im Percent-Format (`# %%`), die `.ipynb` liegt daneben und wird beim Speichern synchronisiert. Du editierst die `.py`; der Mensch öffnet die `.ipynb`.
- **Tests auf Fixtures.** `tests/fixtures/` enthält synthetische Mini-SAP-Tabellen (10–30 Zeilen pro Tabelle), die jeden Fall aus DECISIONS abdecken. Keine Produktivdaten im Repo.
- **Postgres lokal.** Der Devcontainer bringt einen Postgres-Container mit Schema `sap_raw` (Fixtures oder CSV-Exporte geladen) und `basis_bom`. Prod wird nur über `DATABASE_URL` erreicht, nie im Test.
- **Ein Commit pro Phase**, Nachricht nennt die Phase und die erfüllten D-Nummern.

## Phase 1 – Devcontainer und Gerüst

Ziel: `Reopen in Container` → Jupyter läuft, Postgres läuft, Tests laufen.

`.devcontainer/devcontainer.json`:
- Image `mcr.microsoft.com/devcontainers/python:3.12`, `dockerComposeFile: docker-compose.yml`, `service: dev`, `workspaceFolder: /workspaces/ML_Server`
- Features: `ghcr.io/devcontainers/features/docker-in-docker` nur, wenn zwingend; sonst weglassen
- Extensions: `ms-python.python`, `ms-toolsai.jupyter`, `ms-toolsai.jupyter-keymap`, `charliermarsh.ruff`, `mtxr.sqltools` + `mtxr.sqltools-driver-pg`, `congyiwu.vscode-jupytext`
- `forwardPorts: [8888, 5432]`
- `postCreateCommand: pip install -e ".[dev]" && python -m ipykernel install --user --name basis-bom && basis-bom db init --fixtures`
- Settings: Jupyter-Kernel `basis-bom` als Default, `jupyter.notebookFileRoot: ${workspaceFolder}`

`.devcontainer/docker-compose.yml`: Service `dev` (sleep infinity, Workspace gemountet, `DATABASE_URL=postgresql://basis:basis@db:5432/basis`, Export-Ordner aus `EXPORTS_DIR` in `.devcontainer/.env` read-only nach `/data/exports` gemountet), Service `db` (`postgres:16`, Volume, Healthcheck, `shared_buffers` und `work_mem` hochgesetzt – die STPO-CSV hat 1 GB).

`pyproject.toml`: Paket `basis_bom`, Abhängigkeiten `pandas`, `sqlalchemy`, `psycopg[binary]`, `typer`, `pydantic`; `[dev]`: `pytest`, `jupyterlab`, `jupytext`, `ruff`, `ipykernel`. Konsolenskript `basis-bom = basis_bom.cli:app`. Jupytext-Konfiguration: `formats = "ipynb,py:percent"` für `notebooks/`.

Verzeichnisse:
```
basis_bom/          Paket
  cli.py            typer-App: db init | run | check | export | regress
  source.py         Lesezugriff sap_raw mit Stichtag (D14)
  rules.py          Regel-/Alias-/Systemregel-Tabellen laden, Rang auflösen
  parser.py         Bedingungsnamen → (Merkmal, Wert)-Paare
  ranking.py        Entscheidung pro Ebene (D1–D5, D7)
  explode.py        Auflösung mit Bewertung und Spur (D9–D18)
  export.py         SAP-Format (D19)
  regress.py        Abgleich gegen review/bestaetigt (D23)
sql/
  schema/           DDL basis_bom, nummeriert 001_… (idempotent)
  views/            Reports, Stichtag-Views auf sap_raw
  checks/           Konsistenz- und Exportprüfungen
notebooks/          00_exploration_fakten, 10_parser, 20_ranking, 30_explode, 90_debug_material
tests/              pytest + fixtures/
docs/               DECISIONS.md, EXPORT-PLAN.md, dieser Plan
legacy/             basis_bom_v0.py (unverändert)
```

Fertig, wenn: Container startet ohne manuelle Schritte, `pytest` grün (ein Smoke-Test), `notebooks/00_exploration_fakten.py` öffnet sich als Notebook und `SELECT 1` gegen `db` läuft aus einer Zelle.

## Phase 2 – Datenzugriff mit Stichtag

`source.py`: eine Klasse, die jede benötigte Tabelle als DataFrame liefert, gefiltert nach D14 (Löschkennzeichen, `DATUV ≤ Stichtag`, CUKB-Versionswahl über `ADZHL`/`DATUV`/`KNSTA`). Stichtag = `export_datum` der Tabellen; abweichende Daten zwischen Tabellen → Fehler. Fehlt eine Tabelle (siehe EXPORT-PLAN „Übergang"), liefert die Klasse den dokumentierten Ersatz und setzt den Marker.

`basis-bom db init --fixtures` lädt `tests/fixtures/*.csv` nach `sap_raw`; `--from-dir <pfad>` lädt die in `docs/EXPORTE.md` als maßgeblich genannten Dateien. Anforderungen an den Loader:
- Header-Mapping beschreibend → technisch (`ZUORDNUNGSNUMMER` → `KNOBJ`, `INTERNE NUMMER DES WISSENSBAUSTEINS` → `KNNUM`, `BEZIEHUNG` → `KNNAM`, …) als Tabelle in `basis_bom/headers.py`; unbekannte Spalten werden protokolliert, nicht verworfen.
- Trenner (`;`/`,`) und Dezimalkomma erkennen; führende Nullen in `MATNR`/`STLNR`/`KNOBJ`/`KNNUM` einheitlich entfernen.
- **Filter beim Laden**, nicht danach: MARA/MARC/STPO sind Volltabellen (0,3–1 GB); MARC auf `WERKS='4000'`, MAST auf `WERKS='4000'`,`STLAN='1'`, STPO chunkweise auf `STLNR ∈ S`, MARA auf `MATNR ∈ M`. Das ist EXPORT-PLAN Phase 1 in Python – die Schlüsselmengen S/M entstehen hier zuerst.
- `export_datum` je Tabelle aus dem Dateinamen; Lauf-Stichtag = jüngstes Datum mit Warnung bei Abweichung (Dev-Daten), Fehler im Prod-Modus.
- Planzeiten-XLSX → `basis_bom.root_material` (nur Materialnummer, bereinigt, dedupliziert; Rest der Datei bleibt ungeladen); Abgleich gegen `MATERIAL_LIST` aus `legacy/` protokollieren.
- Prüfpunkte 1–5 aus `docs/EXPORTE.md` beim ersten Laden beantworten und in `docs/FRAGEN.md` schreiben.

Fertig, wenn: Fixture mit einer gelöschten, einer zukünftigen und einer doppelt versionierten CUKB-Zeile korrekt gefiltert wird (Test), `db init --from-dir /data/exports` in unter 15 Minuten durchläuft und `notebooks/00_exploration_fakten.py` gegen geladene Daten F1–F6 als Zahlen ausgibt.

## Phase 3 – Schema `basis_bom` und Seeds

DDL in `sql/schema/`:
- `regel(merkmal, wert, status BASIS|NICHT_BASIS|OFFEN, rang int null, begruendung, gueltig_von, gueltig_bis, geaendert_von)` – Constraint: pro (merkmal, gueltig) ist `rang` eindeutig unter `BASIS` (D1, D21)
- `alias(alias, merkmal, status, gueltig_von, gueltig_bis, geaendert_von)` (D6)
- `systemregel` ist keine eigene Tabelle: Einträge in `regel` mit `wert = 'vorhanden'` (D7)
- `root_material(matnr, quelle, geladen_am, gueltig_von, gueltig_bis, geaendert_von)` – Materialliste STO-MON aus der Planzeiten-XLSX (D22)
- `root_ausschluss(matnr, grund, geaendert_von)` (D22)
- `lauf(lauf_id, gestartet, export_datum, regel_version, status, statistik jsonb)` (D21)
- `aufloesung(lauf_id, root_matnr, ebene, stlnr, parent_matnr, matnr, menge, menge_kum, meins, postp, knobj, status, grund, spur jsonb)` (D16–D18)
- `ebene_marker(lauf_id, root_matnr, stlnr, marker, merkmal)` (D4, Ersatzmarker)
- `review(root_matnr, matnr, parent_matnr, urteil richtig|fehlt|gehoert_nicht_rein, kommentar, reviewer, datum)` (D24)
- `bestaetigt(root_matnr, bestaetigt_von, datum)` – Root-Materialien, deren Review vollständig `richtig` ist (D23)

Seeds (`sql/schema/9xx_seed_*.sql`): Aliasse aus `MERKMAL_PATTERNS` des Legacy-Skripts, Regeln aus `DEFAULT_PROFILE`/`MANUAL_DEFAULTS` mit Status `BASIS` und Rang in Reihenfolge der Sets; alle auskommentierten Kandidaten als `OFFEN`. `geaendert_von = 'seed'`.

Fertig, wenn: `basis-bom db init` idempotent läuft, Constraint-Test für doppelten Rang schlägt fehl, Seeds geladen.

## Phase 4 – Parser

`parser.py` portiert `parse_beziehung` mit zwei Änderungen: die Kürzelliste kommt aus `alias` (Reihenfolge längste zuerst, zur Laufzeit gebaut), und das Ergebnis ist ein Objekt mit `paare: list[(merkmal, wert)]`, `unbekannte_aliasse: list[str]`, `roh: str`, `parsbar: bool`. Ein Name ohne einziges `=`/Kürzel ist ein Systemregel-Kandidat: `paare = [(roh, 'vorhanden')]` (D7). Multi-Werte werden zu `wert = 'BS/FK'` belassen, die Aufteilung macht `ranking.py` (D5).

Tests: alle `test_cases` aus dem Legacy-Skript mit erwarteten Ergebnissen, plus je ein Fall für unbekanntes Kürzel, `OPTIK` ohne Suffix, Negation (Ergebnis aus F2 entscheidet, ob Negation `parsbar = False` oder ein eigenes Feld wird – bis dahin `parsbar = False`).

Fertig, wenn: alle Parser-Tests grün und `notebooks/10_parser.py` alle distinct `KNNAM` der geladenen Daten parst und die Verteilung parsbar / unbekannter Alias / Systemregel-Kandidat als Tabelle zeigt.

## Phase 5 – Ranking pro Ebene

`ranking.py`: Eingabe = alle geparsten Bedingungen einer Stückliste + Regelstand. Pro Merkmal: vorkommende Einzelwerte sammeln (Multi-Werte aufspalten), Status nachschlagen, besten `BASIS`-Rang wählen; `SITZHOEHE` numerisch (D3); Ergebnis `gewaehlt: dict[merkmal, wert]` und `marker: list` mit `kein_rang_fuer:<M>` (D4). Prüfung eines Paares gegen `gewaehlt`: enthalten-Semantik für Multi-Werte, unbekannter Teilwert → Flag (D5).

Fertig, wenn: Tests für „X schlägt MANUEL", „nur MANUEL vorhanden → MANUEL", „nur NICHT_BASIS → Marker", `BS/FK` bei gewähltem FK, `HR/XX` mit unbekanntem XX, zwei Ebenen mit unterschiedlicher Wahl (D2) grün sind.

## Phase 6 – Auflösung

`explode.py` ersetzt `explode_variant_bom_single`:
1. Root-Menge = `root_material` minus `root_ausschluss` (D22); Materialien, die die Stammdatenprüfung (konfigurierbar, Stückliste Werk 4000 Verwendung 1) nicht erfüllen, und D15-Verstöße in `lauf.statistik`, übersprungen.
2. BFS mit Pfad, nicht nur `visited` pro Material: ein Material unter zwei Eltern erzeugt zwei Zeilen (D16), wird aber pro Pfad nur einmal weiter aufgelöst.
3. Pro Stückliste: Bedingungen aller Positionen parsen → `ranking` → pro Position alle Auswahlbedingungen (D10 via `KNART`) mit UND prüfen (D9); Prozeduren zählen.
4. Statusvergabe nach D11–D13, Vererbung nach D12.
5. `menge_kum` nach D17, `BMENG` aus STKO oder Ersatzregel.
6. `spur` als JSON nach D18.

Fertig, wenn: Fixture-Root mit 3 Ebenen, einer ausgeschlossenen Baugruppe (Kinder `ausgeschlossen_vererbt`), einer manuellen Position (Kinder `unterhalb_manuell`), einer Prozedur, einer Klassenposition und `BMENG = 2` auf Ebene 2 exakt die erwartete `aufloesung` liefert (Golden-File-Test), und `notebooks/30_explode.py` ein echtes Material Ebene für Ebene mit Spur anzeigt.

## Phase 7 – Reports, Regression, Export

- `sql/views/`: `offene_faelle` (alles `manuell_prüfen` mit Grund, gruppiert nach Ursache), `kein_rang`, `prozeduren`, `statistik_lauf`, `regel_abdeckung` (welche `OFFEN`-Einträge im letzten Lauf tatsächlich vorkamen – das ist die Arbeitsliste für den Fachbereich).
- `regress.py`: für jedes `bestaetigt`-Root Vergleich aktueller Lauf vs. `review` (Menge, Material, Parent); Abweichung = rot, Lauf-Status `regression_fehlgeschlagen`.
- `export.py`: D19 exakt wie `export_grundversion_sap_format` im Legacy-Skript, Kurztext/MArt/SoB aus MAKT/MARA/MARC sofern vorhanden.
- `basis-bom review-export <matnr>`: eine XLSX pro Root-Material für die Fachabteilung – alle Positionen (auch ausgeschlossene, eingeklappt bzw. am Ende), Spalten Ebene, Parent, Material, Kurztext, Menge kumuliert, Status, Grund (lesbar, nicht JSON), plus leere Spalten `Urteil` (richtig / fehlt / gehoert_nicht_rein) und `Kommentar`. `basis-bom review-import <datei>` schreibt ausgefüllte Blätter nach `review`. Das ersetzt für den Prototyp jede Oberfläche.

Fertig, wenn: Regressionstest mit absichtlich geänderter Regel rot wird, Export-Datei aus Fixtures byteweise dem Golden-File entspricht.

## Phase 8 – CLI

`basis-bom run [--matnr …]` führt D23 in der Prototyp-Fassung: `check` (Regel-Constraints, Schlüsselmengen-Abgleich) → Auflösung (alle Root-Materialien oder die angegebenen) → `regress` (nur Meldung) → `export`. Alles, was den Prod-Betrieb betrifft (Webhook, Betriebs-Dockerfile, harte Regression), ist bewusst **nicht** Teil dieses Plans und kommt in einem eigenen Schritt nach dem Fachbereichs-Review.

Fertig, wenn: `basis-bom run --matnr <drei Beispiele>` aus dem Devcontainer in unter fünf Minuten Export und Review-Blätter erzeugt.

## Phase 9 – Debug-Notebook

`notebooks/90_debug_material.py`: Materialnummer eingeben → Baum mit Status, pro Ebene die Rangentscheidung, pro Position die Spur, ausgeschlossene Positionen eingeklappt sichtbar. Das ist die Ansicht, mit der der Mensch Review-Urteile begründet (D24), bevor es eine Oberfläche gibt.

Fertig, wenn: das Notebook für ein Fixture-Root und ein echtes Material ohne Codeänderung läuft.

## Fragen an den Menschen

Sammle sie in `docs/FRAGEN.md` statt zu raten, insbesondere: Ergebnisse F1–F6 mit Konsequenz, jede Stelle, an der DECISIONS keine Antwort gibt, jeder Regel-Seed, dessen Rang du aus der Set-Reihenfolge nur geraten hast.

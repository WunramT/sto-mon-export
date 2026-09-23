# mlp_refa_sto_mon_export – Basis-Stückliste (Prototyp)

Leitet aus SAP-Exporttabellen (Werk 4000, Verwendung 1) die Basis-Version konfigurierbarer Stücklisten ab.
Regeln: `docs/DECISIONS.md`. Plan: `docs/AGENT-PLAN.md`. Offene Fragen und Annahmen: `docs/FRAGEN.md`.

## Start

VS Code → *Reopen in Container*. Der Devcontainer startet Postgres, installiert das Paket, registriert den
Jupyter-Kernel `basis-bom` und lädt die Fixtures. Echte Exporte liegen außerhalb des Repos; Pfad in
`.devcontainer/.env` (`EXPORTS_DIR`, Vorlage `.env.example`), im Container unter `/data/exports`.

```bash
basis-bom db init --from-dir /data/exports   # maßgebliche Exporte laden (docs/EXPORTE.md), Prüfpunkte → docs/FRAGEN.md
basis-bom run --matnr 11071032 --matnr 11071089   # check → Auflösung → regress → Export + Review-Blätter
basis-bom check                                 # Konsistenz- und Exportprüfungen
basis-bom export [--lauf N] [--matnr …]         # SAP-Format (D19)
basis-bom review-export <matnr>…                # Review-Blatt (XLSX) pro Root-Material
basis-bom review-import <datei.xlsx> --reviewer <name>
basis-bom regress [--lauf N]
pytest                                          # Tests (eigene Datenbank <name>_test)
```

Ausgabe unter `out/lauf_<id>/<matnr>/`: `<matnr>_sap_format.csv` und `review_<matnr>.xlsx`. Zur Begründung von
Urteilen: `notebooks/90_debug_material.ipynb` (Materialnummer eintragen, alles ausführen).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `basis_bom/loader.py`, `headers.py` | Exporte lesen, Header mappen, beim Laden filtern (Schlüsselmengen) |
| `basis_bom/source.py` | Lesezugriff `sap_raw` mit Stichtag (D14), Ersatzmarker |
| `basis_bom/rules.py`, `parser.py`, `ranking.py` | Regelstand, Bedingungsnamen, Entscheidung pro Ebene |
| `basis_bom/explode.py`, `lauf.py`, `pipeline.py` | Auflösung mit Spur, Lauf speichern, Prototyp-Lauf |
| `basis_bom/export.py`, `review.py`, `regress.py` | SAP-Format, Review-Blätter, Regression |
| `sql/schema`, `sql/views`, `sql/checks` | DDL + Seeds, Reports, Prüfungen |
| `notebooks/` | jupytext-Paare (`.py` editieren, `.ipynb` öffnen) |
| `tests/fixtures`, `tests/golden` | synthetische Mini-SAP-Tabellen, erwartete Ergebnisse |

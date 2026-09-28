# mlp_refa_sto_mon_export – Basis-Stückliste (Prototyp)

Leitet aus SAP-Exporttabellen (Werk 4000, Verwendung 1) die Basis-Version konfigurierbarer Stücklisten ab.
Regeln: `docs/DECISIONS.md`. Plan: `docs/AGENT-PLAN.md`. Offene Fragen und Annahmen: `docs/FRAGEN.md`.

## Start

VS Code → *Reopen in Container*. Der Devcontainer startet Postgres, installiert das Paket, registriert den
Jupyter-Kernel `basis-bom` und lädt die Fixtures. Echte Exporte liegen außerhalb des Repos; Pfad in
`.devcontainer/.env` (`EXPORTS_DIR`, Vorlage `.env.example`), im Container unter `/data/exports`.

```bash
basis-bom db init --from-dir /data/exports   # maßgebliche Exporte laden (docs/EXPORTE.md), Prüfpunkte → docs/FRAGEN.md
basis-bom ui [--port 8765]                      # Web-Oberfläche für den Fachbereich (Port weiterleiten)
basis-bom run --matnr 11071032 --matnr 11071089   # check → Auflösung → regress → Export
basis-bom check                                 # Konsistenz- und Exportprüfungen
basis-bom export [--lauf N] [--matnr …]         # SAP-Format (D19)
basis-bom regress [--lauf N]
basis-bom regel liste [MERKMAL] | regel setzen … | regel alias …
basis-bom sql "<SELECT …>" [--csv datei]
pytest                                          # Tests (eigene Datenbank <name>_test)
```

Ausgabe unter `out/lauf_<id>/<matnr>/`: `<matnr>_sap_format.csv`. Zur Begründung von
Urteilen: `notebooks/90_debug_material.ipynb` (Materialnummer eintragen, alles ausführen).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `basis_bom/loader.py`, `headers.py` | Exporte lesen, Header mappen, beim Laden filtern (Schlüsselmengen) |
| `basis_bom/source.py` | Lesezugriff `sap_raw` mit Stichtag (D14), Ersatzmarker |
| `basis_bom/rules.py`, `parser.py`, `ranking.py` | Regelstand, Bedingungsnamen, Entscheidung pro Ebene |
| `basis_bom/explode.py`, `lauf.py`, `pipeline.py` | Auflösung mit Spur, Lauf speichern, Prototyp-Lauf |
| `basis_bom/export.py`, `regress.py` | SAP-Format, Regression |
| `basis_bom/ui/` | Web-Oberfläche: `dienst.py` (Logik, Entwurf-Überlagerung), `app.py` (FastAPI), `static/` (ohne CDN) |
| `sql/schema`, `sql/views`, `sql/checks` | DDL + Seeds, Reports, Prüfungen |
| `notebooks/` | jupytext-Paare (`.py` editieren, `.ipynb` öffnen) |
| `tests/fixtures`, `tests/golden` | synthetische Mini-SAP-Tabellen, erwartete Ergebnisse |

## Rollen

Die Anwendung entscheidet nichts fachlich. Der Fachbereich legt fest, welche Werte Basis sind; die Regeln wachsen
Beispiel für Beispiel (D24). Kreislauf:

1. `basis-bom ui` starten, Adresse an den Fachbereich geben (Name wird im Browser gemerkt).
2. Material öffnen: Baum zeigt, welche Positionen in die Basis-Stückliste kommen und warum.
3. Regeln als **Entwurf** ändern (Basis/Offen/Nie Basis, Rang, Kürzel) – Baum rechnet sofort neu;
   „Auswirkung auf alle Materialien“ zeigt die Folgen. Entwurf bleibt je Name auf dem Server erhalten.
4. **Übernehmen** mit Begründung → historisiert (D21); Konflikt, wenn jemand dieselbe Regel inzwischen geändert hat.
5. Material bewerten (Richtig / Sollte raus / Sollte rein, fehlende Materialien ergänzen), speichern, bestätigen.
   Bestätigte Materialien sind Referenz für `basis-bom regress`.
6. `basis-bom run` / `export` → SAP-Format.

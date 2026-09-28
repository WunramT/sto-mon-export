# Offene Punkte (Stand nach Kritik-Runde 6, Bewertung Optik 8/10 · Funktion 8/10)

## Aus der letzten Kritik (reproduziert)

- **P2** Alter ungespeicherter Browser-Stand wird über einen neueren gespeicherten/bestätigten Stand gelegt (gleicher
  Name, zweiter Browser speichert/bestätigt). Folge: „ungespeichert“-Zähler und doppelt gezählte Ergänzung auf einem
  bestätigten Material. Lösung: lokale Einträge beim Laden gegen `review.stand` abgleichen, Ergänzungen entdoppeln,
  bei bestätigten Materialien verwerfen (mit Hinweis). (`frontend/src/stores/arbeit.ts`, `ladeMaterial`)
- **P2** Materialwechsel während eines laufenden Speicherns vermischt zwei Materialien in der Anzeige (Server-Stand
  stimmt). Lösung: in `speichereReview` Material und Speicherschlüssel vor dem `await` festhalten.
- **P2** Klassenposition „rein“, deren ergänztes Material entfernt wurde: Hinweis verweist auf „Ergänzen“, dort ist die
  Klassenposition nicht wählbar. Lösung: Knopf „Material eintragen“ in Details/Hinweis.
- **P2** Anzeige „war: …“ überlappt die Status-Pille (1600 und 1280 px). Lösung: eigene Zeile oder Tooltip.
- **P3** Nach einer Regeländerung ohne Export-Wirkung gelten passende alte Urteile nicht mehr (z. B. „Sollte raus“ →
  jetzt „Nicht in Basis“). Lösung: gleichbedeutende Urteile übernehmen.
- **P3** `export_zeilen` wendet eine manuelle Entscheidung noch an, wenn der Status zwischen den offenen Stati wechselt
  (Oberfläche verwirft sie). Gleiche Regel „Status unverändert“ in beiden verwenden.
- **P3** `/?ansicht=regeln` ohne Material verliert beim Weiterleiten den Reiter.
- **P3** Grüner „Bestätigt“-Chip neben dem orangen „veraltet“-Hinweis.
- **P3** Materialliste anderer offener Sitzungen aktualisiert sich nach fremden Bewertungen erst beim Neuladen.
- **P3** „Menge ges.“ (Oberfläche) vs. „Menge“ je Baugruppe (SAP-Format, D19) – kurzer Hinweis am Export fehlt.

## Fachlich zu bestätigen (Annahmen dieses Prototyps)

- **D25** Manuelle Entscheidung „Sollte rein/raus“ für jede Position „manuell prüfen“ macht das Material bestätigbar.
- **D26** Web-Download = D19 + gespeicherte manuelle Entscheidungen + ergänzte Materialien; CLI-Export bleibt D19.
- Bestätigung „veraltet“ = Fingerabdruck des Exports hat sich geändert.

## Betrieb / Deployment (nicht in dieser Umgebung prüfbar)

- Erster echter Lauf von GitLab-CI (Komponenten buildah/cosign/semgrep, Harbor-Zugang) und Jenkins auf `dpn-svr-iot`
  steht aus; lokal nachgestellt mit `deploy/lokal-deploy.sh`, Jenkinsfile per `deploy/jenkinsfile-pruefen.groovy`.
- Einmalig auf dem Host: DB-Rolle, `sens.env`, Verzeichnisse, Eintrag im Host-nginx (`docs/DEPLOYMENT.md`).
- Laden der echten Exporte (STPO ~1 GB) im Container nicht getestet – Dauer/Speicher prüfen; Postgres-Tuning des
  gemeinsamen Containers (shared_buffers) ggf. anpassen.
- `PUBLIC_BASE_URL` (Standard `https://iot.polipol-service.de`) aus dem MLP-Jenkinsfile übernommen – bestätigen.
- E2E-Tests erwarten frische Beispieldaten (CI: frische Datenbank; lokal `RESET=1 deploy/lokal-deploy.sh`).

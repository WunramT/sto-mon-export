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

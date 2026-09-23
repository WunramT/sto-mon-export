# Export-Plan: SAP-Tabellen verkleinert nach Postgres

Für: das Team, das den nächtlichen SAP→Postgres-Export betreibt. Ziel: alle für `DECISIONS.md` nötigen Tabellen, aber nur der Ausschnitt für Werk 4000 – über **Schlüsselmengen**, nicht über Zeiträume. Zielschema: `sap_raw` (Name anpassen), jede Tabelle mit Spalte `export_datum date`.

Prinzip: erst die kleinen Steuertabellen exportieren, daraus Schlüsselmengen ableiten, damit die großen Tabellen filtern. Dadurch werden STPO, STAS, MAKT und CAWN von Vollabzügen zu Bruchteilen.

## Phase 0 – Bestandsaufnahme (halber Tag)

1. Zeilenzahl und Spaltenliste jeder heute exportierten Tabelle (MAST, STPO, CUOB, CUKB, MARA, MARC) festhalten.
2. Prüfen, ob STPO heute ungefiltert kommt. Wenn ja: das ist der größte Hebel (Phase 2).
3. Prüfen, ob CUKB die Spalten `KNART`, `KNSTA`, `DATUV`, `AENNR`, `LKENZ`, `ADZHL` enthält. Fehlen sie: **zuerst nachziehen** – kein zusätzlicher Export, nur Spalten, aber ohne `KNART` ist D10 nicht umsetzbar.

Fertig, wenn: Tabelle mit Ist-Zeilenzahlen und fehlenden Spalten vorliegt.

## Phase 1 – Schlüsselmengen

Reihenfolge ist zwingend, jede Menge baut auf der vorigen.

| Menge | Definition | Quelle |
|---|---|---|
| **S** (Stücklisten) | `STLNR` aus MAST mit `WERKS='4000'`, `STLAN='1'`, `LKENZ=''` | MAST |
| **P** (Positionen) | Zeilen aus STPO mit `STLNR ∈ S` | STPO |
| **K** (Bedingungsobjekte) | `KNOBJ` aus P, ungleich 0 | STPO |
| **W** (Wissensbausteine) | `KNNUM` aus CUOB mit `KNTAB='STPO'`, `KNOBJ ∈ K` | CUOB |
| **M** (Materialien) | `MATNR` aus MARC `WERKS='4000'` ∪ `IDNRK` aus P | MARC, STPO |
| **A** (Merkmale) | `ATINN` aus CABN mit `ATNAM` in der Merkmalliste (Phase 3) | CABN |

Wo die Exportstrecke keine Joins gegen vorher exportierte Tabellen erlaubt: S und M als Wertelisten in den Selektionsbildschirm/Variante geben und nächtlich aus MAST/MARC regenerieren. S ist typischerweise vier- bis fünfstellig, M fünf- bis sechsstellig – das trägt jede Strecke.

Fertig, wenn: S, P, K, W, M reproduzierbar in Postgres landen und ihre Zeilenzahlen zu Phase 0 passen (P ≪ Voll-STPO).

## Phase 2 – Große Tabellen filtern

Nur genannte Spalten, überall `LKENZ=''` als Filter mitgeben (gelöschte Zeilen braucht niemand).

**STPO** – Filter `STLNR ∈ S`
`STLTY, STLNR, STLKN, STPOZ, POSNR, IDNRK, POSTP, MENGE, MEINS, KNOBJ, ALPGR, ALPRF, DATUV, AENNR, LKENZ`

**STAS** – Filter `STLNR ∈ S`
`STLTY, STLNR, STLAL, STLKN, STASZ, DATUV, AENNR, LKENZ`

**STKO** – Filter `STLNR ∈ S` (klein, eine Zeile pro Stückliste/Version)
`STLTY, STLNR, STLAL, STKOZ, BMENG, BMEIN, STLST, DATUV, AENNR, LOEKZ, LKENZ`

**MAKT** – Filter `MATNR ∈ M`, `SPRAS='D'`
`MATNR, SPRAS, MAKTX`

**MARA** – Filter `MATNR ∈ M`
`MATNR, MATKL, MTART, KZKFG`

**MARC** – Filter `WERKS='4000'`
`MATNR, WERKS, DISPO, SOBSL, BESKZ`

**CUOB** – Filter `KNTAB='STPO'`, `KNOBJ ∈ K`
`KNTAB, KNOBJ, KNNUM, KNSRT, DATUV, AENNR, LKENZ`

**CUKB** – Filter `KNNUM ∈ W`
`KNNUM, ADZHL, KNNAM, KNART, KNSTA, DATUV, AENNR, LKENZ`

**CUKBT** – Filter `KNNUM ∈ W`, `SPRAS='D'` (optional, für den Menschen)
`KNNUM, SPRAS, ADZHL, KNKTX, DATUV, AENNR, LKENZ`

**MAST** – Filter `WERKS='4000'`, `STLAN='1'`
`MATNR, WERKS, STLAN, STLNR, STLAL, DATUV, AENNR, LKENZ`

Fertig, wenn: jede Tabelle in `sap_raw` liegt, `export_datum` gefüllt ist und Phase 4 grün ist.

## Phase 3 – Merkmale und Werte (klein, aber wichtig)

1. Merkmalliste aufstellen: alle kanonischen Merkmalnamen aus der Alias-Tabelle (`RUECKEN_OPTIK`, `RUECKEN_FUNK`, `ARM_OPTIK`, `ARM_L`, `ARM_R`, `SITZQUALI`, `SITZHOEHE`, `SITZTIEFE`, `FUNKTION`, `ELEKTRO`, `GASDRUCK`, `FUSS`, `3_FUSS`, `AKKU`, `MOTOR` – Liste wächst mit der Alias-Tabelle, daher als Postgres-Tabelle pflegen und nächtlich lesen).
2. **CABN** – Filter `ATNAM ∈ Merkmalliste`
   `ATINN, ATNAM, ATFOR, ATEIN, ATSON, DATUV, AENNR, LKENZ`
3. **CAWN** – Filter `ATINN ∈ A`
   `ATINN, ATZHL, ATWRT, ATFLV, ATFLB, ATCOD, DATUV, AENNR, LKENZ`
4. **CAWNT** – Filter `ATINN ∈ A`, `SPRAS='D'`
   `ATINN, ATZHL, SPRAS, ATWTB`

Von Millionen CAWN-Zeilen bleiben einige hundert. `ATSON='X'` bei einem Merkmal heißt: Werte außerhalb CAWN sind erlaubt – dann kann die Rangliste nie vorab vollständig sein, und der Lauf muss unbekannte Werte melden (D8).

Fertig, wenn: für jedes Merkmal der Liste mindestens eine CABN-Zeile und die CAWN-Werte vorliegen.

## Phase 4 – Nachtlauf-Prüfungen (in Postgres, nach jedem Export)

Alle als SQL im Repo (`sql/checks/export_*.sql`), Ergebnis an Node-RED zurück. Rot = Lauf der Basis-Auflösung startet nicht.

1. Zeilenzahl jeder Tabelle > 0 und innerhalb ±20 % des Vortags.
2. Jede `STPO.STLNR` existiert in MAST (S vollständig).
3. Jede `STPO.KNOBJ ≠ 0` hat mindestens eine CUOB-Zeile.
4. Jede `CUOB.KNNUM` hat eine CUKB-Zeile.
5. Jede `STPO.IDNRK` hat eine MARA-Zeile; Anteil ohne MAKT-Zeile < 1 %.
6. Jede `STLNR ∈ S` hat eine STKO-Zeile.
7. `export_datum` aller Tabellen identisch.

Fertig, wenn: alle sieben Prüfungen grün an drei aufeinanderfolgenden Nächten.

## Reihenfolge der Beantragung

Kleinster Aufwand, größter Nutzen zuerst:

1. CUKB-Spalten (`KNART` & Co.) – Spaltenerweiterung, kein neuer Export
2. STPO-Filter auf S – halbiert vermutlich das nächtliche Volumen
3. STKO – klein, schließt D17
4. CABN/CAWN/CAWNT gefiltert – klein, schließt D1/D6 vollständig
5. MAKT gefiltert – Zielformat-Spalte
6. STAS, CUKBT – Gültigkeit und Lesbarkeit

## Übergang: bis die Exporte da sind

Der Lauf startet mit den heutigen Tabellen und diesen Ersatzregeln, jede sichtbar im Report:
- STKO fehlt → `BMENG = 1` angenommen, Marker `bmeng_angenommen`.
- CABN/CAWN fehlen → Rangliste aus beobachteten Werten der Bedingungsnamen befüllt (alle `OFFEN`), Marker `cawn_fehlt`.
- STAS fehlt → Gültigkeit nur über `STPO.LKENZ`/`DATUV`.
- MAKT fehlt → Kurztext leer.
- `CUKB.KNART` fehlt → **kein Übergang möglich**, D10 blockiert. Das ist der einzige harte Blocker.

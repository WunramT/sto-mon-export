-- Reports auf dem letzten abgeschlossenen Lauf (AGENT-PLAN Phase 7). Summen sind Views, nicht Kern (D16).

CREATE OR REPLACE VIEW basis_bom.letzter_lauf AS
SELECT * FROM basis_bom.lauf
WHERE status NOT IN ('laeuft', 'fehler')
ORDER BY lauf_id DESC
LIMIT 1;

-- Alles manuell_prüfen mit Grund, plus Ausschlüsse neben OFFEN-Werten (D8 sichtbar, FRAGEN Q17).
CREATE OR REPLACE VIEW basis_bom.offene_faelle AS
SELECT a.lauf_id, a.root_matnr, a.ebene, a.stlnr, a.posnr, a.parent_matnr, a.matnr, a.status, a.grund,
       CASE
           WHEN a.status = 'ausgeschlossen'            THEN 'ausgeschlossen_neben_offen'
           WHEN a.grund LIKE 'kein_rang_fuer:%'        THEN 'kein_rang'
           WHEN a.grund LIKE '%nicht parsbar%'         THEN 'nicht_parsbar'
           WHEN a.grund LIKE '%unbekanntes Kürzel%'    THEN 'unbekanntes_kuerzel'
           WHEN a.grund LIKE '%nicht eindeutig/OFFEN%' THEN 'kuerzel_offen'
           WHEN a.grund LIKE 'unbekannter_teilwert:%'  THEN 'unbekannter_teilwert'
           WHEN a.grund LIKE 'Klassenposition%'        THEN 'klassenposition'
           WHEN a.grund LIKE 'Datenfehler:%'           THEN 'datenfehler'
           WHEN a.grund LIKE 'D15:%'                   THEN 'd15_mehrere_stlnr'
           WHEN a.grund LIKE '%KNART%'                 THEN 'knart_unbekannt'
           WHEN a.grund LIKE 'Positionstyp%'           THEN 'positionstyp'
           WHEN a.grund LIKE 'Zyklus%' OR a.grund LIKE 'maximale Tiefe%' THEN 'struktur'
           ELSE 'sonstiges'
       END AS ursache
FROM basis_bom.aufloesung a
JOIN basis_bom.letzter_lauf l USING (lauf_id)
WHERE a.status = 'manuell_prüfen'
   OR (a.status = 'ausgeschlossen' AND a.grund LIKE '%Status OFFEN/unbekannt%');

CREATE OR REPLACE VIEW basis_bom.offene_faelle_ursache AS
SELECT ursache, count(*) AS positionen, count(DISTINCT root_matnr) AS root_materialien,
       (array_agg(grund ORDER BY grund))[1:5] AS beispiele
FROM basis_bom.offene_faelle
GROUP BY ursache
ORDER BY positionen DESC;

-- D4: Stücklisten ohne Rangwert pro Merkmal.
CREATE OR REPLACE VIEW basis_bom.kein_rang AS
SELECT m.merkmal, count(DISTINCT m.stlnr) AS stuecklisten, count(DISTINCT m.root_matnr) AS root_materialien,
       (SELECT count(*) FROM basis_bom.aufloesung a
         WHERE a.lauf_id = l.lauf_id AND a.grund LIKE '%kein_rang_fuer:' || m.merkmal || '%') AS positionen
FROM basis_bom.ebene_marker m
JOIN basis_bom.letzter_lauf l USING (lauf_id)
WHERE m.marker LIKE 'kein_rang_fuer:%'
GROUP BY m.merkmal, l.lauf_id
ORDER BY positionen DESC;

-- D10: ignorierte Prozeduren.
CREATE OR REPLACE VIEW basis_bom.prozeduren AS
SELECT p.prozedur, count(*) AS positionen, count(DISTINCT a.root_matnr) AS root_materialien
FROM basis_bom.aufloesung a
JOIN basis_bom.letzter_lauf l USING (lauf_id)
CROSS JOIN LATERAL jsonb_array_elements_text(a.spur -> 'prozeduren') AS p(prozedur)
GROUP BY p.prozedur
ORDER BY positionen DESC;

-- Kennzahlen pro Lauf.
CREATE OR REPLACE VIEW basis_bom.statistik_lauf AS
SELECT l.lauf_id, l.gestartet, l.beendet, l.status, l.export_datum, l.regel_version,
       count(a.*) AS positionen,
       count(*) FILTER (WHERE a.status = 'basis') AS basis,
       count(*) FILTER (WHERE a.status = 'unbedingt') AS unbedingt,
       count(*) FILTER (WHERE a.status = 'ausgeschlossen') AS ausgeschlossen,
       count(*) FILTER (WHERE a.status = 'ausgeschlossen_vererbt') AS ausgeschlossen_vererbt,
       count(*) FILTER (WHERE a.status = 'manuell_prüfen') AS manuell_pruefen,
       count(*) FILTER (WHERE a.status = 'unterhalb_manuell') AS unterhalb_manuell,
       count(*) FILTER (WHERE a.status = 'ignoriert') AS ignoriert,
       count(DISTINCT a.root_matnr) AS root_materialien,
       l.statistik -> 'aufloesung' -> 'marker' AS marker,
       jsonb_array_length(coalesce(l.statistik -> 'aufloesung' -> 'roots_uebersprungen', '[]')) AS roots_uebersprungen
FROM basis_bom.lauf l
LEFT JOIN basis_bom.aufloesung a USING (lauf_id)
GROUP BY l.lauf_id
ORDER BY l.lauf_id DESC;

-- Arbeitsliste für den Fachbereich: welche OFFEN-Einträge kamen im letzten Lauf tatsächlich vor.
CREATE OR REPLACE VIEW basis_bom.regel_abdeckung AS
WITH vorkommen AS (
    SELECT a.root_matnr, a.stlnr, a.matnr, p ->> 0 AS merkmal, w AS wert
    FROM basis_bom.aufloesung a
    JOIN basis_bom.letzter_lauf l USING (lauf_id)
    CROSS JOIN LATERAL jsonb_array_elements(a.spur -> 'beziehungen') AS b
    CROSS JOIN LATERAL jsonb_array_elements(coalesce(b -> 'paare', '[]')) AS p
    CROSS JOIN LATERAL regexp_split_to_table(p ->> 1, '[/+]') AS w
)
SELECT r.merkmal, r.wert, r.status, r.begruendung, r.geaendert_von,
       count(v.*) AS positionen,
       count(DISTINCT v.stlnr) AS stuecklisten,
       count(DISTINCT v.root_matnr) AS root_materialien,
       count(v.*) > 0 AS im_letzten_lauf
FROM basis_bom.regel r
LEFT JOIN vorkommen v ON v.merkmal = r.merkmal AND v.wert = r.wert
WHERE r.status = 'OFFEN' AND r.gueltig_bis IS NULL
GROUP BY r.id
ORDER BY positionen DESC, r.merkmal, r.wert;

-- D16: Summen pro Root und Material (nur exportierte Status).
CREATE OR REPLACE VIEW basis_bom.summe_material AS
SELECT a.lauf_id, a.root_matnr, a.matnr, a.meins, sum(a.menge_kum) AS menge_kum, count(*) AS vorkommen
FROM basis_bom.aufloesung a
WHERE a.status IN ('basis', 'unbedingt')
GROUP BY a.lauf_id, a.root_matnr, a.matnr, a.meins;

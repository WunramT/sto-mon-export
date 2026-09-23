-- EXPORT-PLAN Phase 4.5: Anteil IDNRK ohne MAKT-Zeile < 1 %.
SELECT 'export: STPO.IDNRK mit MAKT (≥ 99 %)' AS pruefung,
       coalesce(avg((m.matnr IS NULL)::int), 0) < 0.01 AS ok,
       round(100 * coalesce(avg((m.matnr IS NULL)::int), 0), 2) || ' % ohne Kurztext' AS detail
FROM (SELECT DISTINCT idnrk FROM sap_raw.stpo WHERE coalesce(idnrk, '') <> '') p
LEFT JOIN (SELECT DISTINCT matnr FROM sap_raw.makt) m ON m.matnr = p.idnrk;

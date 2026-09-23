-- EXPORT-PLAN Phase 4.5: jede STPO.IDNRK hat eine MARA-Zeile; Anteil ohne MAKT < 1 %.
SELECT 'export: STPO.IDNRK in MARA' AS pruefung, count(*) = 0 AS ok, count(*) || ' IDNRK ohne MARA' AS detail
FROM (SELECT DISTINCT idnrk FROM sap_raw.stpo WHERE coalesce(idnrk, '') <> '') p
WHERE NOT EXISTS (SELECT 1 FROM sap_raw.mara m WHERE m.matnr = p.idnrk);

-- EXPORT-PLAN Phase 4.2: jede STPO.STLNR existiert in MAST (S vollständig).
SELECT 'export: STPO.STLNR in MAST' AS pruefung, count(*) = 0 AS ok, count(*) || ' STLNR ohne MAST' AS detail
FROM (SELECT DISTINCT stlnr FROM sap_raw.stpo) p
WHERE NOT EXISTS (SELECT 1 FROM sap_raw.mast m WHERE m.stlnr = p.stlnr);

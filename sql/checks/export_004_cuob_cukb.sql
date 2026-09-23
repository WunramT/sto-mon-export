-- EXPORT-PLAN Phase 4.4: jede CUOB.KNNUM hat eine CUKB-Zeile.
SELECT 'export: CUOB.KNNUM in CUKB' AS pruefung, count(*) = 0 AS ok, count(*) || ' KNNUM ohne CUKB' AS detail
FROM (SELECT DISTINCT knnum FROM sap_raw.cuob) c
WHERE NOT EXISTS (SELECT 1 FROM sap_raw.cukb k WHERE k.knnum = c.knnum);

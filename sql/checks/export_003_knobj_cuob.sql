-- EXPORT-PLAN Phase 4.3: jede STPO.KNOBJ ≠ 0 hat mindestens eine CUOB-Zeile.
SELECT 'export: STPO.KNOBJ in CUOB' AS pruefung, count(*) = 0 AS ok, count(*) || ' KNOBJ ohne CUOB' AS detail
FROM (SELECT DISTINCT knobj FROM sap_raw.stpo WHERE coalesce(knobj, '') NOT IN ('', '0')) p
WHERE NOT EXISTS (SELECT 1 FROM sap_raw.cuob c WHERE c.knobj = p.knobj);

-- EXPORT-PLAN Phase 4.6: jede STLNR ∈ S hat eine STKO-Zeile.
SELECT 'export: STLNR in STKO' AS pruefung, count(*) = 0 AS ok, count(*) || ' STLNR ohne STKO' AS detail
FROM (SELECT DISTINCT stlnr FROM sap_raw.mast WHERE coalesce(lkenz, '') = '') s
WHERE NOT EXISTS (SELECT 1 FROM sap_raw.stko k WHERE k.stlnr = s.stlnr);

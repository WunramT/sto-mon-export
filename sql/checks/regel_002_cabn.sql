-- D6: kanonischer Name = CABN.ATNAM (nur, wenn CABN geladen ist).
SELECT 'alias: kanonische Merkmale in CABN' AS pruefung,
       count(*) = 0 AS ok,
       coalesce(string_agg(DISTINCT a.merkmal, ', '), '') AS detail
FROM basis_bom.alias a
WHERE a.status = 'BASIS' AND a.gueltig_bis IS NULL
  AND NOT EXISTS (SELECT 1 FROM sap_raw.cabn c WHERE c.atnam = a.merkmal);

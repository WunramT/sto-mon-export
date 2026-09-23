-- Regel-/Alias-Konsistenz (D1, D6). Spalten: pruefung, ok, detail.
SELECT 'regel: BASIS-Ränge lückenlos ab 1' AS pruefung,
       count(*) = 0 AS ok,
       coalesce(string_agg(merkmal || ' ' || raenge, '; '), '') AS detail
FROM (
    SELECT merkmal, array_agg(rang ORDER BY rang)::text AS raenge
    FROM basis_bom.regel WHERE status = 'BASIS' AND gueltig_bis IS NULL
    GROUP BY merkmal
    HAVING max(rang) <> count(*) OR min(rang) <> 1
) x
UNION ALL
SELECT 'alias: BASIS-Alias mit Merkmal', count(*) = 0, coalesce(string_agg(alias, ', '), '')
FROM basis_bom.alias WHERE status = 'BASIS' AND merkmal IS NULL AND gueltig_bis IS NULL
UNION ALL
SELECT 'regel: OFFEN-Einträge (Information)', true, count(*)::text
FROM basis_bom.regel WHERE status = 'OFFEN' AND gueltig_bis IS NULL
UNION ALL
SELECT 'alias: OFFEN-Kürzel (Information)', true, coalesce(string_agg(alias, ', ' ORDER BY alias), '')
FROM basis_bom.alias WHERE status = 'OFFEN' AND gueltig_bis IS NULL;

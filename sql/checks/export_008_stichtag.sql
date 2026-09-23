-- EXPORT-PLAN Phase 4.7: export_datum aller Tabellen identisch (Dev-Daten: Warnung, siehe docs/EXPORTE.md).
SELECT 'export: export_datum identisch' AS pruefung,
       count(DISTINCT export_datum) <= 1 AS ok,
       coalesce(string_agg(tabelle || '=' || export_datum, ', ' ORDER BY tabelle), '') AS detail
FROM (
    SELECT DISTINCT ON (tabelle) tabelle, export_datum FROM basis_bom.ladeprotokoll ORDER BY tabelle, id DESC
) x;

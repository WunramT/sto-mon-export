-- EXPORT-PLAN Phase 4.1: Zeilenzahl > 0 und innerhalb ±20 % des vorigen Ladens.
SELECT 'export: Zeilenzahl ' || tabelle AS pruefung,
       zeilen_geladen > 0 AND (vorher IS NULL OR abs(zeilen_geladen - vorher) <= 0.2 * vorher) AS ok,
       zeilen_geladen || ' Zeilen' || coalesce(' (vorher ' || vorher || ')', '') AS detail
FROM (
    SELECT DISTINCT ON (tabelle) tabelle, zeilen_geladen,
           lag(zeilen_geladen) OVER (PARTITION BY tabelle ORDER BY id) AS vorher
    FROM basis_bom.ladeprotokoll
    ORDER BY tabelle, id DESC
) x;

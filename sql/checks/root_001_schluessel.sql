-- D22: jedes Root-Material hat eine Stückliste Werk 4000 / Verwendung 1 (Schlüsselmengen-Abgleich).
SELECT 'root_material: Stückliste 4000/1 vorhanden' AS pruefung,
       count(*) = 0 AS ok,
       count(*) || ' ohne MAST: ' || coalesce(string_agg(r.matnr, ', ' ORDER BY r.matnr) FILTER (WHERE rn <= 20), '')
           AS detail
FROM (
    SELECT r.matnr, row_number() OVER (ORDER BY r.matnr) AS rn
    FROM basis_bom.root_material r
    WHERE r.gueltig_bis IS NULL
      AND NOT EXISTS (SELECT 1 FROM sap_raw.mast m WHERE m.matnr = r.matnr AND coalesce(m.lkenz, '') = '')
) r;

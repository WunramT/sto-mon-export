-- Seeds Alias-Tabelle (D6) aus MERKMAL_PATTERNS in legacy/basis_bom_v0.py.
-- OPTIK/ARM ohne Suffix werden nicht geraten (D6) → OFFEN, ohne Merkmal.
INSERT INTO basis_bom.alias (alias, merkmal, status, geaendert_von)
SELECT v.alias, v.merkmal, v.status, 'seed' FROM (VALUES
    ('RUECKEN_OPTIK', 'RUECKEN_OPTIK', 'BASIS'),
    ('RUECKEN_FUNK', 'RUECKEN_FUNK', 'BASIS'),
    ('RUECK_FUNK', 'RUECKEN_FUNK', 'BASIS'),
    ('ARM_OPTIK', 'ARM_OPTIK', 'BASIS'),
    ('ARM_OPT', 'ARM_OPTIK', 'BASIS'),
    ('ARM_L', 'ARM_L', 'BASIS'),
    ('ARM_R', 'ARM_R', 'BASIS'),
    ('SITZQUALI', 'SITZQUALI', 'BASIS'),
    ('SIQUALI', 'SITZQUALI', 'BASIS'),
    ('SITZHOEHE', 'SITZHOEHE', 'BASIS'),
    ('SITZTIEFE', 'SITZTIEFE', 'BASIS'),
    ('SITZTIEF', 'SITZTIEFE', 'BASIS'),
    ('SITZQ', 'SITZQUALI', 'BASIS'),
    ('SITZH', 'SITZHOEHE', 'BASIS'),
    ('SITZHO', 'SITZHOEHE', 'BASIS'),
    ('FUNKTION', 'FUNKTION', 'BASIS'),
    ('ELEKTRO', 'ELEKTRO', 'BASIS'),
    ('GASDRUCK', 'GASDRUCK', 'BASIS'),
    ('3_FUSS', '3_FUSS', 'BASIS'),
    ('RUECK', 'RUECKEN_FUNK', 'BASIS'),
    ('RUCK', 'RUECKEN_FUNK', 'BASIS'),
    ('FUNK', 'FUNKTION', 'BASIS'),
    ('ELEK', 'ELEKTRO', 'BASIS'),
    ('AKKU', 'AKKU', 'BASIS'),
    ('FUSS', 'FUSS', 'BASIS'),
    ('MOTOR', 'MOTOR', 'BASIS'),
    ('OPTIK', NULL, 'OFFEN'),
    ('ARM', NULL, 'OFFEN'),
    ('SQ', 'SITZQUALI', 'BASIS'),
    ('SH', 'SITZHOEHE', 'BASIS'),
    ('E', 'ELEKTRO', 'BASIS'),
    ('F', 'FUNKTION', 'BASIS')
) AS v(alias, merkmal, status)
WHERE NOT EXISTS (SELECT 1 FROM basis_bom.alias x WHERE x.alias = v.alias AND x.gueltig_bis IS NULL);

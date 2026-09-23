-- Seeds Regeltabelle (D1) aus legacy/basis_bom_v0.py.
-- DEFAULT_PROFILE → BASIS Rang 1. MANUAL_DEFAULTS → BASIS, Rang in Reihenfolge der Set-Einträge im Quelltext
-- (geraten, siehe docs/FRAGEN.md Q10). Auskommentierte Kandidaten → OFFEN.
-- MOTOR, GASDRUCK, FUSS, 3_FUSS, SITZTIEFE: keine Defaults im Legacy-Skript → keine Seeds.
-- SITZHOEHE: numerischer Rang (D3), keine Seeds nötig.
INSERT INTO basis_bom.regel (merkmal, wert, status, rang, begruendung, geaendert_von)
SELECT v.merkmal, v.wert, v.status, v.rang, v.begruendung, 'seed' FROM (VALUES
    ('RUECKEN_OPTIK', 'A',      'BASIS', 1,    'Legacy DEFAULT_PROFILE'),
    ('ARM_OPTIK',     '1',      'BASIS', 1,    'Legacy DEFAULT_PROFILE'),
    ('SITZQUALI',     'HR',     'BASIS', 1,    'Legacy DEFAULT_PROFILE'),
    ('FUNKTION',      'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS: Grundfunktion (allgemein)'),
    ('FUNKTION',      'MANUEL', 'BASIS', 2,    'Legacy MANUAL_DEFAULTS: Manuell (z.B. manuelle Verstellung)'),
    ('FUNKTION',      'BK',     'BASIS', 3,    'Legacy MANUAL_DEFAULTS: Körperdruck'),
    ('FUNKTION',      'WA1',    'OFFEN', NULL, 'Legacy auskommentiert: wenn WA1 auch Grundversion sein kann'),
    ('FUNKTION',      'VZMO',   'OFFEN', NULL, 'Legacy auskommentiert: bei Bedarf'),
    ('RUECKEN_FUNK',  'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS: Standard-Rückenfunktion'),
    ('RUECKEN_FUNK',  'ST',     'BASIS', 2,    'Legacy MANUAL_DEFAULTS: Starr (einfachste Variante)'),
    ('RUECKEN_FUNK',  'KV',     'OFFEN', NULL, 'Legacy auskommentiert: wenn Kopfverstellung Standard'),
    ('ELEKTRO',       'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS: ohne spezielle Elektro-Ausstattung'),
    ('ELEKTRO',       'FA',     'OFFEN', NULL, 'Legacy auskommentiert: bei Bedarf'),
    ('AKKU',          'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS'),
    ('ARM_L',         'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS: Standard-Armlehne'),
    ('ARM_L',         'LAL',    'OFFEN', NULL, 'Legacy auskommentiert: wenn LAL auch Grundversion'),
    ('ARM_R',         'X',      'BASIS', 1,    'Legacy MANUAL_DEFAULTS: Standard-Armlehne'),
    ('ARM_R',         'LAL',    'OFFEN', NULL, 'Legacy auskommentiert')
) AS v(merkmal, wert, status, rang, begruendung)
WHERE NOT EXISTS (
    SELECT 1 FROM basis_bom.regel r WHERE r.merkmal = v.merkmal AND r.wert = v.wert AND r.gueltig_bis IS NULL
);

-- Regelwerk (D1, D6, D7, D8, D21). Systemregeln sind Einträge in regel mit wert = 'vorhanden' (D7).
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS basis_bom.regel (
    id            bigserial PRIMARY KEY,
    merkmal       text NOT NULL,
    wert          text NOT NULL,
    status        text NOT NULL CHECK (status IN ('BASIS', 'NICHT_BASIS', 'OFFEN')),
    rang          int,
    begruendung   text,
    gueltig_von   timestamptz NOT NULL DEFAULT now(),
    gueltig_bis   timestamptz,
    geaendert_von text NOT NULL,
    CONSTRAINT regel_rang_nur_basis CHECK ((status = 'BASIS') = (rang IS NOT NULL)),
    CONSTRAINT regel_zeitraum CHECK (gueltig_bis IS NULL OR gueltig_bis > gueltig_von)
);

DO $$
BEGIN
    -- D1/D21: pro Merkmal und Gültigkeitszeitraum ist ein Rang unter BASIS eindeutig.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'regel_rang_eindeutig') THEN
        ALTER TABLE basis_bom.regel ADD CONSTRAINT regel_rang_eindeutig EXCLUDE USING gist (
            merkmal WITH =, rang WITH =, tstzrange(gueltig_von, gueltig_bis) WITH &&
        ) WHERE (status = 'BASIS');
    END IF;
    -- Ein Wert hat zu jedem Zeitpunkt genau einen Status.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'regel_wert_eindeutig') THEN
        ALTER TABLE basis_bom.regel ADD CONSTRAINT regel_wert_eindeutig EXCLUDE USING gist (
            merkmal WITH =, wert WITH =, tstzrange(gueltig_von, gueltig_bis) WITH &&
        );
    END IF;
END $$;

-- D6: Merkmalkürzel → kanonischer Name (= CABN.ATNAM). Status wie D8: nur BASIS-Aliasse gelten als geklärt.
CREATE TABLE IF NOT EXISTS basis_bom.alias (
    id            bigserial PRIMARY KEY,
    alias         text NOT NULL,
    merkmal       text,
    status        text NOT NULL CHECK (status IN ('BASIS', 'NICHT_BASIS', 'OFFEN')),
    gueltig_von   timestamptz NOT NULL DEFAULT now(),
    gueltig_bis   timestamptz,
    geaendert_von text NOT NULL,
    CONSTRAINT alias_zeitraum CHECK (gueltig_bis IS NULL OR gueltig_bis > gueltig_von)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'alias_eindeutig') THEN
        ALTER TABLE basis_bom.alias ADD CONSTRAINT alias_eindeutig EXCLUDE USING gist (
            alias WITH =, tstzrange(gueltig_von, gueltig_bis) WITH &&
        );
    END IF;
END $$;

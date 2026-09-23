-- Laden der Exporte (AGENT-PLAN Phase 2): Protokoll und Root-Materialien (D22).

CREATE TABLE IF NOT EXISTS basis_bom.ladeprotokoll (
    id                 bigserial PRIMARY KEY,
    geladen_am         timestamptz NOT NULL DEFAULT now(),
    tabelle            text NOT NULL,
    datei              text NOT NULL,
    export_datum       date,
    zeilen_roh         bigint,
    zeilen_geladen     bigint,
    unbekannte_spalten text[],
    fehlende_spalten   text[],
    hinweise           text[]
);

-- D22: Materialliste STO-MON aus der Planzeiten-XLSX; historisiert (D21).
CREATE TABLE IF NOT EXISTS basis_bom.root_material (
    matnr         text NOT NULL,
    quelle        text NOT NULL,
    geladen_am    timestamptz NOT NULL DEFAULT now(),
    gueltig_von   timestamptz NOT NULL DEFAULT now(),
    gueltig_bis   timestamptz,
    geaendert_von text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS root_material_aktiv ON basis_bom.root_material (matnr) WHERE gueltig_bis IS NULL;

-- D22: fachlich ausgeschlossene Root-Materialien.
CREATE TABLE IF NOT EXISTS basis_bom.root_ausschluss (
    matnr         text PRIMARY KEY,
    grund         text NOT NULL,
    geaendert_von text NOT NULL,
    geaendert_am  timestamptz NOT NULL DEFAULT now()
);

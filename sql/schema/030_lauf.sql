-- Läufe und Ergebnis (D16–D18, D21).
CREATE TABLE IF NOT EXISTS basis_bom.lauf (
    lauf_id       bigserial PRIMARY KEY,
    gestartet     timestamptz NOT NULL DEFAULT now(),
    beendet       timestamptz,
    export_datum  date,
    regel_version timestamptz,
    status        text NOT NULL DEFAULT 'laeuft',
    statistik     jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- D16: eine Zeile pro Vorkommen. lfd/pfad/posnr halten Reihenfolge und Pfad fest.
CREATE TABLE IF NOT EXISTS basis_bom.aufloesung (
    lauf_id      bigint NOT NULL REFERENCES basis_bom.lauf ON DELETE CASCADE,
    root_matnr   text NOT NULL,
    lfd          int NOT NULL,
    ebene        int NOT NULL,
    stlnr        text NOT NULL,
    posnr        text,
    parent_matnr text NOT NULL,
    matnr        text NOT NULL,
    menge        numeric,
    menge_kum    numeric,
    meins        text,
    postp        text,
    knobj        text,
    status       text NOT NULL CHECK (status IN ('basis', 'unbedingt', 'ausgeschlossen', 'ausgeschlossen_vererbt',
                                                 'manuell_prüfen', 'unterhalb_manuell', 'ignoriert')),
    grund        text,
    pfad         text NOT NULL,
    spur         jsonb NOT NULL,
    PRIMARY KEY (lauf_id, root_matnr, lfd)
);
CREATE INDEX IF NOT EXISTS aufloesung_status ON basis_bom.aufloesung (lauf_id, status);

-- D4 und Ersatzmarker pro Stückliste und Lauf.
CREATE TABLE IF NOT EXISTS basis_bom.ebene_marker (
    lauf_id    bigint NOT NULL REFERENCES basis_bom.lauf ON DELETE CASCADE,
    root_matnr text NOT NULL,
    stlnr      text NOT NULL,
    marker     text NOT NULL,
    merkmal    text
);
CREATE INDEX IF NOT EXISTS ebene_marker_lauf ON basis_bom.ebene_marker (lauf_id, marker);

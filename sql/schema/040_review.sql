-- Review durch den Fachbereich (D23, D24).
CREATE TABLE IF NOT EXISTS basis_bom.review (
    id           bigserial PRIMARY KEY,
    root_matnr   text NOT NULL,
    matnr        text NOT NULL,
    parent_matnr text NOT NULL,
    menge        numeric,  -- menge_kum zum Zeitpunkt des Reviews, Vergleichsgröße der Regression (D23)
    urteil       text NOT NULL CHECK (urteil IN ('richtig', 'fehlt', 'gehoert_nicht_rein')),
    kommentar    text,
    status       text,  -- Status der Zeile im Review-Blatt; „richtig“ bezieht sich darauf
    reviewer     text NOT NULL,
    datum        date NOT NULL DEFAULT current_date,
    lauf_id      bigint,  -- Lauf, aus dem das Review-Blatt erzeugt wurde
    importiert   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS review_root ON basis_bom.review (root_matnr);

-- Root-Materialien, deren Review vollständig „richtig“ ist.
CREATE TABLE IF NOT EXISTS basis_bom.bestaetigt (
    root_matnr     text PRIMARY KEY,
    bestaetigt_von text NOT NULL,
    datum          date NOT NULL DEFAULT current_date
);

ALTER TABLE basis_bom.review ADD COLUMN IF NOT EXISTS status text;

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
-- Web-Oberfläche: Urteil bezieht sich auf die Zeile (Pfad) eines Laufs; ergänzte Materialien („fehlt“) ohne Status.
ALTER TABLE basis_bom.review ADD COLUMN IF NOT EXISTS pfad text;

-- Web-Oberfläche: Regel-Entwurf pro Person (überlebt Neuladen und Browserwechsel; wirkt erst nach „Übernehmen“).
CREATE TABLE IF NOT EXISTS basis_bom.entwurf (
    name      text PRIMARY KEY,
    daten     jsonb NOT NULL,
    geaendert timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE basis_bom.review ADD COLUMN IF NOT EXISTS meins text;

-- Web-Oberfläche: Anzeigename je Merkmal (vom Fachbereich pflegbar; ohne Eintrag wird der SAP-Name gezeigt).
-- Startwerte sind aus den SAP-Namen abgeleitet (Annahme) und in der Oberfläche änderbar.
CREATE TABLE IF NOT EXISTS basis_bom.merkmal_text (
    merkmal text PRIMARY KEY,
    text    text NOT NULL
);
INSERT INTO basis_bom.merkmal_text (merkmal, text) VALUES
    ('SITZQUALI', 'Sitzqualität'), ('SITZHOEHE', 'Sitzhöhe'), ('SITZTIEFE', 'Sitztiefe'),
    ('FUNKTION', 'Funktion'), ('AKKU', 'Akku'), ('ELEKTRO', 'Elektrik'),
    ('ARM_L', 'Armteil links'), ('ARM_R', 'Armteil rechts'), ('ARM_OPTIK', 'Armoptik'),
    ('RUECKEN_FUNK', 'Rückenfunktion'), ('RUECKEN_OPTIK', 'Rückenoptik')
ON CONFLICT (merkmal) DO NOTHING;

-- Fingerabdruck des SAP-Format-Exports zum Zeitpunkt der Bestätigung (D26): „veraltet“, wenn der Export heute
-- anders aussähe – nicht schon, wenn sich nur ein Status ändert, der am Export nichts ändert.
ALTER TABLE basis_bom.bestaetigt ADD COLUMN IF NOT EXISTS export_stand text;

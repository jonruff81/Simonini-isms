-- Create table for extracted figure images
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_figures (
    figure_id SERIAL PRIMARY KEY,
    figure_code VARCHAR(50) NOT NULL,          -- e.g., "30-100-35-001"
    phase_code VARCHAR(20) NOT NULL,           -- e.g., "30-100"
    document_id INTEGER REFERENCES takeoff.isms_spec_documents(document_id),
    page_number INTEGER,                        -- PDF page where figure appears
    image_path VARCHAR(500),                    -- Path to extracted image file
    image_data BYTEA,                           -- Or store image directly in DB
    width INTEGER,
    height INTEGER,
    caption TEXT,                               -- Any caption text found near figure
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(figure_code)
);

CREATE INDEX IF NOT EXISTS idx_spec_figures_phase ON takeoff.isms_spec_figures(phase_code);
CREATE INDEX IF NOT EXISTS idx_spec_figures_code ON takeoff.isms_spec_figures(figure_code);

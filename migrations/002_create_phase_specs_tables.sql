-- Phase Specs Content Tables
-- Stores extracted content from Phase Spec PDFs for browsable reference

-- Phase Spec Documents (one per PDF)
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_documents (
    document_id SERIAL PRIMARY KEY,
    phase_code VARCHAR(20) NOT NULL,          -- e.g., "30-500"
    phase_name VARCHAR(255) NOT NULL,         -- e.g., "Alarm System"
    full_title VARCHAR(255) NOT NULL,         -- e.g., "Phase 30-500 Alarm System"
    jobtread_file_id VARCHAR(50),             -- JobTread file ID
    jobtread_url TEXT,                        -- CDN URL
    file_size INTEGER,                        -- bytes
    page_count INTEGER,                       -- number of pages
    summary TEXT,                             -- AI-generated or manual summary
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phase_code)
);

-- Phase Spec Sections (e.g., "Bids for Work", "Work Requirements")
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_sections (
    section_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES takeoff.isms_spec_documents(document_id) ON DELETE CASCADE,
    section_name VARCHAR(255) NOT NULL,       -- e.g., "Work Requirements"
    section_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase Spec Items (numbered requirements within sections)
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_items (
    item_id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES takeoff.isms_spec_sections(section_id) ON DELETE CASCADE,
    item_number VARCHAR(20),                  -- e.g., "1", "2", "3a"
    item_text TEXT NOT NULL,                  -- The requirement text
    item_html TEXT,                           -- HTML formatted version
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User bookmarks for spec items (similar to isms_bookmarks)
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_bookmarks (
    bookmark_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES takeoff.users(user_id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES takeoff.isms_spec_items(item_id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- User notes for spec items
CREATE TABLE IF NOT EXISTS takeoff.isms_spec_notes (
    note_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES takeoff.users(user_id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES takeoff.isms_spec_items(item_id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_spec_documents_phase_code ON takeoff.isms_spec_documents(phase_code);
CREATE INDEX IF NOT EXISTS idx_spec_sections_document_id ON takeoff.isms_spec_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_spec_items_section_id ON takeoff.isms_spec_items(section_id);
CREATE INDEX IF NOT EXISTS idx_spec_bookmarks_user_id ON takeoff.isms_spec_bookmarks(user_id);
CREATE INDEX IF NOT EXISTS idx_spec_notes_user_id ON takeoff.isms_spec_notes(user_id);

-- Full text search index on item text
CREATE INDEX IF NOT EXISTS idx_spec_items_text_search ON takeoff.isms_spec_items
    USING gin(to_tsvector('english', item_text));

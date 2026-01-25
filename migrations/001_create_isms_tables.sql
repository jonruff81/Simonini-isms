-- Simonini-isms Database Schema
-- Run against the shared takeoff_pricing_db database
-- Tables are prefixed with isms_ and live in the takeoff schema

-- ============================================
-- PHASES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_phases (
    phase_id SERIAL PRIMARY KEY,
    phase_code VARCHAR(20) NOT NULL UNIQUE,
    phase_name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES takeoff.users(user_id),
    updated_by INTEGER REFERENCES takeoff.users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_isms_phases_code ON takeoff.isms_phases(phase_code);
CREATE INDEX IF NOT EXISTS idx_isms_phases_sort ON takeoff.isms_phases(sort_order);
CREATE INDEX IF NOT EXISTS idx_isms_phases_active ON takeoff.isms_phases(is_active);

-- ============================================
-- RULES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_rules (
    rule_id SERIAL PRIMARY KEY,
    phase_id INTEGER NOT NULL REFERENCES takeoff.isms_phases(phase_id) ON DELETE CASCADE,
    rule_number INTEGER NOT NULL,
    rule_text TEXT NOT NULL,
    rule_html TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES takeoff.users(user_id),
    updated_by INTEGER REFERENCES takeoff.users(user_id),
    UNIQUE(phase_id, rule_number)
);

CREATE INDEX IF NOT EXISTS idx_isms_rules_phase ON takeoff.isms_rules(phase_id);
CREATE INDEX IF NOT EXISTS idx_isms_rules_active ON takeoff.isms_rules(is_active);

-- Full text search index on rule_text
CREATE INDEX IF NOT EXISTS idx_isms_rules_text_search ON takeoff.isms_rules USING gin(to_tsvector('english', rule_text));

-- ============================================
-- RULE VERSIONS TABLE (Version History)
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_rule_versions (
    version_id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES takeoff.isms_rules(rule_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    rule_text TEXT NOT NULL,
    rule_html TEXT,
    change_summary VARCHAR(500),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by INTEGER REFERENCES takeoff.users(user_id),
    UNIQUE(rule_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_isms_versions_rule ON takeoff.isms_rule_versions(rule_id);
CREATE INDEX IF NOT EXISTS idx_isms_versions_date ON takeoff.isms_rule_versions(changed_at);

-- ============================================
-- USER BOOKMARKS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_bookmarks (
    bookmark_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES takeoff.users(user_id) ON DELETE CASCADE,
    rule_id INTEGER NOT NULL REFERENCES takeoff.isms_rules(rule_id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_isms_bookmarks_user ON takeoff.isms_bookmarks(user_id);
CREATE INDEX IF NOT EXISTS idx_isms_bookmarks_rule ON takeoff.isms_bookmarks(rule_id);

-- ============================================
-- USER HIGHLIGHTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_highlights (
    highlight_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES takeoff.users(user_id) ON DELETE CASCADE,
    rule_id INTEGER NOT NULL REFERENCES takeoff.isms_rules(rule_id) ON DELETE CASCADE,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    highlighted_text TEXT NOT NULL,
    highlight_color VARCHAR(20) DEFAULT 'yellow',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_isms_highlights_user ON takeoff.isms_highlights(user_id);
CREATE INDEX IF NOT EXISTS idx_isms_highlights_rule ON takeoff.isms_highlights(rule_id);

-- ============================================
-- USER NOTES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_notes (
    note_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES takeoff.users(user_id) ON DELETE CASCADE,
    rule_id INTEGER NOT NULL REFERENCES takeoff.isms_rules(rule_id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_isms_notes_user ON takeoff.isms_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_isms_notes_rule ON takeoff.isms_notes(rule_id);

-- ============================================
-- TAGS SYSTEM (Optional)
-- ============================================
CREATE TABLE IF NOT EXISTS takeoff.isms_tags (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) NOT NULL UNIQUE,
    tag_color VARCHAR(20) DEFAULT '#6c757d',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS takeoff.isms_rule_tags (
    rule_id INTEGER NOT NULL REFERENCES takeoff.isms_rules(rule_id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES takeoff.isms_tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY(rule_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_isms_rule_tags_tag ON takeoff.isms_rule_tags(tag_id);

-- ============================================
-- TRIGGERS FOR updated_at
-- ============================================
CREATE OR REPLACE FUNCTION takeoff.isms_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS isms_phases_updated ON takeoff.isms_phases;
CREATE TRIGGER isms_phases_updated
    BEFORE UPDATE ON takeoff.isms_phases
    FOR EACH ROW EXECUTE FUNCTION takeoff.isms_update_timestamp();

DROP TRIGGER IF EXISTS isms_rules_updated ON takeoff.isms_rules;
CREATE TRIGGER isms_rules_updated
    BEFORE UPDATE ON takeoff.isms_rules
    FOR EACH ROW EXECUTE FUNCTION takeoff.isms_update_timestamp();

DROP TRIGGER IF EXISTS isms_notes_updated ON takeoff.isms_notes;
CREATE TRIGGER isms_notes_updated
    BEFORE UPDATE ON takeoff.isms_notes
    FOR EACH ROW EXECUTE FUNCTION takeoff.isms_update_timestamp();

-- ============================================
-- GRANT PERMISSIONS
-- ============================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA takeoff TO "Jon";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA takeoff TO "Jon";

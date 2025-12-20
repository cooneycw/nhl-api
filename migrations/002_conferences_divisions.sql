-- Migration: 002_conferences_divisions.sql
-- Description: Conference and division hierarchy tables
-- Author: Claude Code
-- Date: 2025-12-20

-- Conferences table
CREATE TABLE IF NOT EXISTS conferences (
    conference_id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    abbreviation VARCHAR(10),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_conferences_updated_at
    BEFORE UPDATE ON conferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Divisions table (FK to conferences)
CREATE TABLE IF NOT EXISTS divisions (
    division_id INTEGER PRIMARY KEY,
    conference_id INTEGER REFERENCES conferences(conference_id),
    name VARCHAR(50) NOT NULL,
    abbreviation VARCHAR(10),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_divisions_conference ON divisions(conference_id);

CREATE TRIGGER update_divisions_updated_at
    BEFORE UPDATE ON divisions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert current NHL conferences
INSERT INTO conferences (conference_id, name, abbreviation)
VALUES
    (5, 'Western', 'W'),
    (6, 'Eastern', 'E')
ON CONFLICT (conference_id) DO NOTHING;

-- Insert current NHL divisions
INSERT INTO divisions (division_id, conference_id, name, abbreviation)
VALUES
    (15, 6, 'Atlantic', 'A'),
    (16, 5, 'Central', 'C'),
    (17, 6, 'Metropolitan', 'M'),
    (18, 5, 'Pacific', 'P')
ON CONFLICT (division_id) DO NOTHING;

COMMENT ON TABLE conferences IS 'NHL conference definitions (Eastern/Western)';
COMMENT ON TABLE divisions IS 'NHL division definitions linked to conferences';

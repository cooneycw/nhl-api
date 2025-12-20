-- Migration: 001_seasons.sql
-- Description: Core season reference table for NHL API
-- Author: Claude Code
-- Date: 2025-12-20

-- Seasons table: Foundation for all season-based data
-- Example: 20242025 represents the 2024-2025 NHL season
CREATE TABLE IF NOT EXISTS seasons (
    season_id INTEGER PRIMARY KEY,  -- Format: YYYYYYYY (e.g., 20242025)
    start_year SMALLINT NOT NULL,
    end_year SMALLINT NOT NULL,
    regular_season_start DATE,
    regular_season_end DATE,
    playoffs_start DATE,
    playoffs_end DATE,
    season_type VARCHAR(20) DEFAULT 'regular',  -- regular, lockout, shortened
    games_scheduled INTEGER,
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_years CHECK (end_year = start_year + 1),
    CONSTRAINT valid_season_id CHECK (
        season_id = (start_year * 10000) + end_year
    )
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_seasons_current ON seasons(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_seasons_years ON seasons(start_year, end_year);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_seasons_updated_at
    BEFORE UPDATE ON seasons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert target seasons for this project
INSERT INTO seasons (season_id, start_year, end_year, is_current)
VALUES
    (20232024, 2023, 2024, FALSE),
    (20242025, 2024, 2025, TRUE)
ON CONFLICT (season_id) DO NOTHING;

COMMENT ON TABLE seasons IS 'NHL season reference data with date ranges and metadata';
COMMENT ON COLUMN seasons.season_id IS 'Unique season identifier in YYYYYYYY format (e.g., 20242025)';

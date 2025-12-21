-- Migration: 013_standings_snapshots.sql
-- Description: Daily standings snapshots for historical tracking
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #126

-- Standings snapshots table: captures daily standings for all teams
CREATE TABLE IF NOT EXISTS standings_snapshots (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,  -- Team abbreviation (e.g., "BOS")
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,

    -- Conference/Division info
    conference_abbrev VARCHAR(5),
    conference_name VARCHAR(50),
    division_abbrev VARCHAR(5),
    division_name VARCHAR(50),

    -- Core record
    games_played INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    ot_losses INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    point_pctg FLOAT,

    -- Goals
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    goal_differential INTEGER DEFAULT 0,

    -- Win types
    regulation_wins INTEGER DEFAULT 0,
    regulation_plus_ot_wins INTEGER DEFAULT 0,
    shootout_wins INTEGER DEFAULT 0,
    shootout_losses INTEGER DEFAULT 0,

    -- Rankings
    league_sequence INTEGER,
    conference_sequence INTEGER,
    division_sequence INTEGER,
    wildcard_sequence INTEGER,

    -- Streak (stored as string like "W3", "L2", "OT1")
    streak_code VARCHAR(5),
    streak_count INTEGER,

    -- Record splits (stored as strings for simplicity)
    home_record VARCHAR(20),   -- "15-5-2"
    road_record VARCHAR(20),   -- "10-8-3"
    last_10_record VARCHAR(20), -- "6-3-1"

    -- Playoff status
    clinch_indicator VARCHAR(5),  -- x=playoff, y=division, z=presidents, e=eliminated

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one entry per team per date per season
    UNIQUE(team_abbrev, season_id, snapshot_date)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_date
    ON standings_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_season
    ON standings_snapshots(season_id);
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_team
    ON standings_snapshots(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_season_date
    ON standings_snapshots(season_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_division
    ON standings_snapshots(division_abbrev, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_standings_snapshots_conference
    ON standings_snapshots(conference_abbrev, snapshot_date);

COMMENT ON TABLE standings_snapshots IS 'Daily snapshots of NHL standings for historical tracking and analysis';
COMMENT ON COLUMN standings_snapshots.snapshot_date IS 'Date when this standings snapshot was captured';
COMMENT ON COLUMN standings_snapshots.clinch_indicator IS 'Playoff clinch status: x=playoff spot, y=division, z=presidents trophy, e=eliminated';

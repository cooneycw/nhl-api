-- Migration: 014_team_rosters.sql
-- Description: Team roster snapshots for tracking player-team assignments by season
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #125

-- Team roster snapshots: tracks which players are on each team's roster for a season
-- This captures the roster state at a point in time, including position assignments
CREATE TABLE IF NOT EXISTS team_rosters (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,  -- Team abbreviation (e.g., "BOS")
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    player_id INTEGER NOT NULL REFERENCES players(player_id),

    -- Position and roster info
    position_code VARCHAR(2) NOT NULL,  -- L, R, C, D, G
    sweater_number INTEGER,
    roster_type VARCHAR(20) NOT NULL,  -- forward, defenseman, goalie

    -- Snapshot metadata
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one entry per player per team per season per snapshot date
    UNIQUE(team_abbrev, season_id, player_id, snapshot_date)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_team_rosters_team
    ON team_rosters(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_team_rosters_season
    ON team_rosters(season_id);
CREATE INDEX IF NOT EXISTS idx_team_rosters_player
    ON team_rosters(player_id);
CREATE INDEX IF NOT EXISTS idx_team_rosters_team_season
    ON team_rosters(team_abbrev, season_id);
CREATE INDEX IF NOT EXISTS idx_team_rosters_snapshot_date
    ON team_rosters(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_team_rosters_position
    ON team_rosters(position_code);

CREATE TRIGGER update_team_rosters_updated_at
    BEFORE UPDATE ON team_rosters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE team_rosters IS 'Team roster snapshots tracking player assignments by season';
COMMENT ON COLUMN team_rosters.roster_type IS 'Player category: forward, defenseman, or goalie';
COMMENT ON COLUMN team_rosters.snapshot_date IS 'Date when this roster snapshot was captured';

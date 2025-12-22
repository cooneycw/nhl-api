-- Migration: 022_dailyfaceoff.sql
-- Description: Tables for DailyFaceoff external data sources
-- Author: Claude Code
-- Date: 2025-12-22
-- Issue: #237

-- This migration creates tables for storing:
-- 1. DailyFaceoff line combinations (forward lines, defensive pairs, goalies)
-- 2. DailyFaceoff power play units (PP1, PP2)
-- 3. DailyFaceoff penalty kill units (PK1, PK2)
-- 4. DailyFaceoff injuries
-- 5. DailyFaceoff starting goalies (tonight's games)

-- =============================================================================
-- DailyFaceoff Line Combinations
-- =============================================================================

-- Line combination snapshots: daily player position assignments
CREATE TABLE IF NOT EXISTS df_line_combinations (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Player identification (nullable - may not match NHL player)
    player_name VARCHAR(100) NOT NULL,
    player_id INTEGER REFERENCES players(player_id),  -- NHL player_id if linked
    df_player_id VARCHAR(20),  -- DailyFaceoff's internal player ID
    jersey_number INTEGER,

    -- Position assignment
    line_type VARCHAR(20) NOT NULL,  -- 'forward', 'defense', 'goalie'
    unit_number INTEGER NOT NULL,    -- 1-4 for forwards, 1-3 for defense, 1-2 for goalies
    position_code VARCHAR(5) NOT NULL,  -- 'lw', 'c', 'rw', 'ld', 'rd', 'g'

    -- Injury indicator from lineup page
    injury_status VARCHAR(20),  -- 'ir', 'out', 'day-to-day', etc.

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique: one position per player per team per date
    UNIQUE(team_abbrev, snapshot_date, player_name, line_type, unit_number, position_code)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_df_line_comb_team ON df_line_combinations(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_df_line_comb_date ON df_line_combinations(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_line_comb_season ON df_line_combinations(season_id);
CREATE INDEX IF NOT EXISTS idx_df_line_comb_player ON df_line_combinations(player_id) WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_df_line_comb_team_date ON df_line_combinations(team_abbrev, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_line_comb_line_type ON df_line_combinations(line_type, unit_number);

CREATE TRIGGER update_df_line_combinations_updated_at
    BEFORE UPDATE ON df_line_combinations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE df_line_combinations IS 'DailyFaceoff even-strength line combinations by team and date';
COMMENT ON COLUMN df_line_combinations.line_type IS 'forward (lines 1-4), defense (pairs 1-3), or goalie (starter/backup)';
COMMENT ON COLUMN df_line_combinations.unit_number IS 'Line/pair number: 1-4 for forwards, 1-3 for defense, 1-2 for goalies';
COMMENT ON COLUMN df_line_combinations.position_code IS 'Position: lw, c, rw for forwards; ld, rd for defense; g for goalies';
COMMENT ON COLUMN df_line_combinations.df_player_id IS 'DailyFaceoff internal player ID for cross-reference';


-- =============================================================================
-- DailyFaceoff Power Play Units
-- =============================================================================

-- Power play unit snapshots: PP1 and PP2 configurations
CREATE TABLE IF NOT EXISTS df_power_play_units (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Unit assignment
    unit_number INTEGER NOT NULL CHECK (unit_number IN (1, 2)),  -- PP1 or PP2

    -- Player information
    player_name VARCHAR(100) NOT NULL,
    player_id INTEGER REFERENCES players(player_id),
    df_player_id VARCHAR(20),
    jersey_number INTEGER,
    position_code VARCHAR(5) NOT NULL,  -- 'sk1', 'sk2', 'sk3', 'sk4', 'sk5'

    -- DailyFaceoff ratings and stats
    df_rating DECIMAL(5, 2),  -- 0-100 rating from DailyFaceoff
    season_goals INTEGER,
    season_assists INTEGER,
    season_points INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_abbrev, snapshot_date, unit_number, player_name)
);

CREATE INDEX IF NOT EXISTS idx_df_pp_team ON df_power_play_units(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_df_pp_date ON df_power_play_units(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_pp_season ON df_power_play_units(season_id);
CREATE INDEX IF NOT EXISTS idx_df_pp_player ON df_power_play_units(player_id) WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_df_pp_team_date ON df_power_play_units(team_abbrev, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_pp_unit ON df_power_play_units(team_abbrev, unit_number);

CREATE TRIGGER update_df_power_play_units_updated_at
    BEFORE UPDATE ON df_power_play_units
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE df_power_play_units IS 'DailyFaceoff power play unit configurations (PP1, PP2) by team and date';
COMMENT ON COLUMN df_power_play_units.unit_number IS '1 for PP1, 2 for PP2';
COMMENT ON COLUMN df_power_play_units.position_code IS 'Skater position: sk1-sk5 (DailyFaceoff convention)';
COMMENT ON COLUMN df_power_play_units.df_rating IS 'DailyFaceoff player rating (0-100 scale)';


-- =============================================================================
-- DailyFaceoff Penalty Kill Units
-- =============================================================================

-- Penalty kill unit snapshots: PK1 and PK2 configurations
CREATE TABLE IF NOT EXISTS df_penalty_kill_units (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Unit assignment
    unit_number INTEGER NOT NULL CHECK (unit_number IN (1, 2)),  -- PK1 or PK2

    -- Player information
    player_name VARCHAR(100) NOT NULL,
    player_id INTEGER REFERENCES players(player_id),
    df_player_id VARCHAR(20),
    jersey_number INTEGER,
    position_type VARCHAR(10) NOT NULL,  -- 'forward' or 'defense'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_abbrev, snapshot_date, unit_number, player_name)
);

CREATE INDEX IF NOT EXISTS idx_df_pk_team ON df_penalty_kill_units(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_df_pk_date ON df_penalty_kill_units(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_pk_season ON df_penalty_kill_units(season_id);
CREATE INDEX IF NOT EXISTS idx_df_pk_player ON df_penalty_kill_units(player_id) WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_df_pk_team_date ON df_penalty_kill_units(team_abbrev, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_pk_unit ON df_penalty_kill_units(team_abbrev, unit_number);

CREATE TRIGGER update_df_penalty_kill_units_updated_at
    BEFORE UPDATE ON df_penalty_kill_units
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE df_penalty_kill_units IS 'DailyFaceoff penalty kill unit configurations (PK1, PK2) by team and date';
COMMENT ON COLUMN df_penalty_kill_units.unit_number IS '1 for PK1, 2 for PK2';
COMMENT ON COLUMN df_penalty_kill_units.position_type IS 'forward (2 per unit) or defense (2 per unit)';


-- =============================================================================
-- DailyFaceoff Injuries
-- =============================================================================

-- Injury snapshots: tracks player injuries over time
CREATE TABLE IF NOT EXISTS df_injuries (
    id SERIAL PRIMARY KEY,
    team_abbrev VARCHAR(10) NOT NULL,
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Player information
    player_name VARCHAR(100) NOT NULL,
    player_id INTEGER REFERENCES players(player_id),
    df_player_id VARCHAR(20),

    -- Injury details
    injury_type VARCHAR(50),  -- 'upper-body', 'lower-body', 'concussion', etc.
    injury_status VARCHAR(30) NOT NULL,  -- 'ir', 'day-to-day', 'out', 'questionable', 'game-time-decision'
    expected_return VARCHAR(100),  -- 'Week-to-week', 'Day-to-day', etc.
    injury_details TEXT,  -- Full description

    -- Timestamp from DailyFaceoff (when they updated it)
    df_updated_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_abbrev, snapshot_date, player_name)
);

CREATE INDEX IF NOT EXISTS idx_df_injuries_team ON df_injuries(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_df_injuries_date ON df_injuries(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_injuries_season ON df_injuries(season_id);
CREATE INDEX IF NOT EXISTS idx_df_injuries_player ON df_injuries(player_id) WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_df_injuries_team_date ON df_injuries(team_abbrev, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_df_injuries_status ON df_injuries(injury_status);
CREATE INDEX IF NOT EXISTS idx_df_injuries_active ON df_injuries(snapshot_date, injury_status)
    WHERE injury_status IN ('ir', 'out', 'day-to-day');

CREATE TRIGGER update_df_injuries_updated_at
    BEFORE UPDATE ON df_injuries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE df_injuries IS 'DailyFaceoff injury reports by team and date';
COMMENT ON COLUMN df_injuries.injury_status IS 'ir, day-to-day, out, questionable, game-time-decision';
COMMENT ON COLUMN df_injuries.expected_return IS 'Timeline text (e.g., Week-to-week, Indefinite)';
COMMENT ON COLUMN df_injuries.df_updated_at IS 'When DailyFaceoff last updated this injury record';


-- =============================================================================
-- DailyFaceoff Starting Goalies
-- =============================================================================

-- Starting goalie predictions for tonight's games
CREATE TABLE IF NOT EXISTS df_starting_goalies (
    id SERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Team information
    team_abbrev VARCHAR(10) NOT NULL,
    opponent_abbrev VARCHAR(10) NOT NULL,
    is_home BOOLEAN NOT NULL,

    -- Game time
    game_time TIMESTAMP WITH TIME ZONE,

    -- Goalie information
    goalie_name VARCHAR(100) NOT NULL,
    goalie_id INTEGER REFERENCES players(player_id),
    df_goalie_id INTEGER,  -- DailyFaceoff goalie ID

    -- Confirmation status
    confirmation_status VARCHAR(20) NOT NULL,  -- 'confirmed', 'likely', 'unconfirmed'

    -- Season stats from DailyFaceoff
    wins INTEGER,
    losses INTEGER,
    otl INTEGER,
    save_pct DECIMAL(5, 4),  -- 0.9234
    gaa DECIMAL(4, 2),  -- 2.45
    shutouts INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(game_date, team_abbrev, goalie_name)
);

CREATE INDEX IF NOT EXISTS idx_df_starters_date ON df_starting_goalies(game_date);
CREATE INDEX IF NOT EXISTS idx_df_starters_team ON df_starting_goalies(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_df_starters_goalie ON df_starting_goalies(goalie_id) WHERE goalie_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_df_starters_status ON df_starting_goalies(confirmation_status);
CREATE INDEX IF NOT EXISTS idx_df_starters_game ON df_starting_goalies(game_date, team_abbrev, opponent_abbrev);

CREATE TRIGGER update_df_starting_goalies_updated_at
    BEFORE UPDATE ON df_starting_goalies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE df_starting_goalies IS 'DailyFaceoff starting goalie predictions for tonight''s games';
COMMENT ON COLUMN df_starting_goalies.confirmation_status IS 'confirmed (official), likely (expected), unconfirmed';
COMMENT ON COLUMN df_starting_goalies.df_goalie_id IS 'DailyFaceoff internal goalie ID';


-- =============================================================================
-- Add Data Sources for DailyFaceoff
-- =============================================================================

INSERT INTO data_sources (name, source_type, base_url, description, rate_limit_ms) VALUES
    ('dailyfaceoff_lines', 'dailyfaceoff', 'https://www.dailyfaceoff.com',
     'DailyFaceoff line combinations', 1000),
    ('dailyfaceoff_power_play', 'dailyfaceoff', 'https://www.dailyfaceoff.com',
     'DailyFaceoff power play unit configurations', 1000),
    ('dailyfaceoff_penalty_kill', 'dailyfaceoff', 'https://www.dailyfaceoff.com',
     'DailyFaceoff penalty kill unit configurations', 1000),
    ('dailyfaceoff_injuries', 'dailyfaceoff', 'https://www.dailyfaceoff.com',
     'DailyFaceoff injury reports', 1000),
    ('dailyfaceoff_starting_goalies', 'dailyfaceoff', 'https://www.dailyfaceoff.com',
     'DailyFaceoff starting goalie predictions', 1000)
ON CONFLICT (name) DO NOTHING;

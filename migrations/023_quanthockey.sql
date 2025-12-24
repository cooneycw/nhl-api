-- Migration: 023_quanthockey.sql
-- Description: Tables for QuantHockey player statistics
-- Author: Claude Code
-- Date: 2025-12-22
-- Issue: #238

-- This migration creates tables for storing:
-- 1. QuantHockey player season statistics (51 fields)
-- 2. Daily snapshots for tracking stat changes over time

-- =============================================================================
-- QuantHockey Player Season Statistics
-- =============================================================================

-- Player season stats: comprehensive 51-field statistics from QuantHockey
CREATE TABLE IF NOT EXISTS qh_player_season_stats (
    id SERIAL PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    snapshot_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Core Identity (11 fields)
    rank INTEGER NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    team_abbrev VARCHAR(10) NOT NULL,
    age INTEGER,
    position VARCHAR(5) NOT NULL,  -- C, LW, RW, D, G
    games_played INTEGER NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    pim INTEGER NOT NULL DEFAULT 0,  -- Penalty minutes
    plus_minus INTEGER NOT NULL DEFAULT 0,

    -- Player linking (optional - may not match NHL player)
    player_id INTEGER REFERENCES players(player_id),

    -- Time on Ice (4 fields) - in minutes per game
    toi_avg DECIMAL(5, 2) DEFAULT 0,
    toi_es DECIMAL(5, 2) DEFAULT 0,   -- Even-strength
    toi_pp DECIMAL(5, 2) DEFAULT 0,   -- Power-play
    toi_sh DECIMAL(5, 2) DEFAULT 0,   -- Short-handed

    -- Goal Breakdowns (5 fields)
    es_goals INTEGER DEFAULT 0,
    pp_goals INTEGER DEFAULT 0,
    sh_goals INTEGER DEFAULT 0,
    gw_goals INTEGER DEFAULT 0,   -- Game-winning
    ot_goals INTEGER DEFAULT 0,   -- Overtime

    -- Assist Breakdowns (5 fields)
    es_assists INTEGER DEFAULT 0,
    pp_assists INTEGER DEFAULT 0,
    sh_assists INTEGER DEFAULT 0,
    gw_assists INTEGER DEFAULT 0,
    ot_assists INTEGER DEFAULT 0,

    -- Point Breakdowns (6 fields)
    es_points INTEGER DEFAULT 0,
    pp_points INTEGER DEFAULT 0,
    sh_points INTEGER DEFAULT 0,
    gw_points INTEGER DEFAULT 0,
    ot_points INTEGER DEFAULT 0,
    ppp_pct DECIMAL(5, 2) DEFAULT 0,  -- Power-play points percentage

    -- Per-60 Rates - All Situations (3 fields)
    goals_per_60 DECIMAL(5, 2) DEFAULT 0,
    assists_per_60 DECIMAL(5, 2) DEFAULT 0,
    points_per_60 DECIMAL(5, 2) DEFAULT 0,

    -- Per-60 Rates - Even-Strength (3 fields)
    es_goals_per_60 DECIMAL(5, 2) DEFAULT 0,
    es_assists_per_60 DECIMAL(5, 2) DEFAULT 0,
    es_points_per_60 DECIMAL(5, 2) DEFAULT 0,

    -- Per-60 Rates - Power-Play (3 fields)
    pp_goals_per_60 DECIMAL(5, 2) DEFAULT 0,
    pp_assists_per_60 DECIMAL(5, 2) DEFAULT 0,
    pp_points_per_60 DECIMAL(5, 2) DEFAULT 0,

    -- Per-Game Rates (3 fields)
    goals_per_game DECIMAL(5, 3) DEFAULT 0,
    assists_per_game DECIMAL(5, 3) DEFAULT 0,
    points_per_game DECIMAL(5, 3) DEFAULT 0,

    -- Shooting Statistics (2 fields)
    shots_on_goal INTEGER DEFAULT 0,
    shooting_pct DECIMAL(5, 2) DEFAULT 0,

    -- Physical Play (2 fields)
    hits INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,

    -- Faceoff Statistics (3 fields)
    faceoffs_won INTEGER DEFAULT 0,
    faceoffs_lost INTEGER DEFAULT 0,
    faceoff_pct DECIMAL(5, 2) DEFAULT 0,

    -- Additional Metadata (1 field)
    nationality VARCHAR(10),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique: one entry per player per season per snapshot date
    UNIQUE(season_id, snapshot_date, player_name, team_abbrev)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_qh_stats_season ON qh_player_season_stats(season_id);
CREATE INDEX IF NOT EXISTS idx_qh_stats_date ON qh_player_season_stats(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_qh_stats_player_name ON qh_player_season_stats(player_name);
CREATE INDEX IF NOT EXISTS idx_qh_stats_team ON qh_player_season_stats(team_abbrev);
CREATE INDEX IF NOT EXISTS idx_qh_stats_position ON qh_player_season_stats(position);
CREATE INDEX IF NOT EXISTS idx_qh_stats_player ON qh_player_season_stats(player_id) WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_qh_stats_season_date ON qh_player_season_stats(season_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_qh_stats_points ON qh_player_season_stats(season_id, points DESC);
CREATE INDEX IF NOT EXISTS idx_qh_stats_goals ON qh_player_season_stats(season_id, goals DESC);

-- Scoring leaders index for quick leaderboard queries
CREATE INDEX IF NOT EXISTS idx_qh_stats_leaders ON qh_player_season_stats(season_id, snapshot_date, points DESC, goals DESC);

CREATE TRIGGER update_qh_player_season_stats_updated_at
    BEFORE UPDATE ON qh_player_season_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE qh_player_season_stats IS 'QuantHockey 51-field player season statistics with daily snapshots';
COMMENT ON COLUMN qh_player_season_stats.rank IS 'Ranking in QuantHockey scoring leaders';
COMMENT ON COLUMN qh_player_season_stats.snapshot_date IS 'Date this data was scraped (for tracking changes)';
COMMENT ON COLUMN qh_player_season_stats.toi_avg IS 'Average TOI per game in minutes';
COMMENT ON COLUMN qh_player_season_stats.ppp_pct IS 'Power-play points as percentage of total points';
COMMENT ON COLUMN qh_player_season_stats.player_id IS 'NHL player_id if linked (nullable - QuantHockey names may differ)';


-- =============================================================================
-- Add Data Source for QuantHockey
-- =============================================================================

INSERT INTO data_sources (name, source_type, base_url, description, rate_limit_ms) VALUES
    ('quanthockey_player_stats', 'quanthockey', 'https://www.quanthockey.com',
     'QuantHockey player season statistics (51 fields)', 2000)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    rate_limit_ms = EXCLUDED.rate_limit_ms;


-- =============================================================================
-- View: Latest QuantHockey Stats per Player
-- =============================================================================

-- Get the most recent snapshot for each player in a season
CREATE OR REPLACE VIEW v_qh_latest_stats AS
SELECT DISTINCT ON (season_id, player_name, team_abbrev)
    id,
    season_id,
    snapshot_date,
    fetched_at,
    rank,
    player_name,
    team_abbrev,
    age,
    position,
    games_played,
    goals,
    assists,
    points,
    pim,
    plus_minus,
    player_id,
    toi_avg,
    toi_es,
    toi_pp,
    toi_sh,
    es_goals,
    pp_goals,
    sh_goals,
    gw_goals,
    ot_goals,
    es_assists,
    pp_assists,
    sh_assists,
    gw_assists,
    ot_assists,
    es_points,
    pp_points,
    sh_points,
    gw_points,
    ot_points,
    ppp_pct,
    goals_per_60,
    assists_per_60,
    points_per_60,
    es_goals_per_60,
    es_assists_per_60,
    es_points_per_60,
    pp_goals_per_60,
    pp_assists_per_60,
    pp_points_per_60,
    goals_per_game,
    assists_per_game,
    points_per_game,
    shots_on_goal,
    shooting_pct,
    hits,
    blocked_shots,
    faceoffs_won,
    faceoffs_lost,
    faceoff_pct,
    nationality
FROM qh_player_season_stats
ORDER BY season_id, player_name, team_abbrev, snapshot_date DESC;

COMMENT ON VIEW v_qh_latest_stats IS 'Most recent QuantHockey snapshot for each player per season';


-- =============================================================================
-- View: QuantHockey Scoring Leaders
-- =============================================================================

CREATE OR REPLACE VIEW v_qh_scoring_leaders AS
SELECT
    season_id,
    snapshot_date,
    rank,
    player_name,
    team_abbrev,
    position,
    games_played,
    goals,
    assists,
    points,
    plus_minus,
    points_per_game,
    pp_points,
    ppp_pct
FROM v_qh_latest_stats
ORDER BY season_id DESC, points DESC, goals DESC;

COMMENT ON VIEW v_qh_scoring_leaders IS 'QuantHockey scoring leaders by season';

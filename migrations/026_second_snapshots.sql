-- Migration: 026_second_snapshots.sql
-- Description: Second-by-second analytics snapshots for granular player tracking
-- Author: Claude Code
-- Date: 2026-01-11
-- Issue: #259 - Wave 1: Core Pipeline

-- Second snapshots: One row per second of game time with all on-ice players
-- Designed for ~94M rows per season (3600 seconds × ~1300 games × variable players)
CREATE TABLE IF NOT EXISTS second_snapshots (
    -- Primary key: composite for efficient partitioning
    snapshot_id BIGSERIAL PRIMARY KEY,

    -- Game reference
    game_id BIGINT NOT NULL,
    season_id INTEGER NOT NULL,

    -- Time reference
    period INTEGER NOT NULL,           -- 1, 2, 3, 4 (OT), 5 (2OT/SO)
    period_second INTEGER NOT NULL,    -- 0-1200 (seconds within period)
    game_second INTEGER NOT NULL,      -- 0-3600+ (total elapsed seconds)

    -- Situation tracking
    situation_code VARCHAR(10) NOT NULL,  -- "5v5", "5v4", "4v5", "3v3", "EN5v4", etc.
    home_skater_count INTEGER NOT NULL DEFAULT 5,
    away_skater_count INTEGER NOT NULL DEFAULT 5,

    -- Player tracking (using arrays for efficient storage)
    home_skater_ids BIGINT[] NOT NULL DEFAULT '{}',
    away_skater_ids BIGINT[] NOT NULL DEFAULT '{}',
    home_goalie_id BIGINT,            -- NULL if empty net
    away_goalie_id BIGINT,            -- NULL if empty net

    -- State flags
    is_stoppage BOOLEAN DEFAULT FALSE,     -- Play stopped (faceoff pending, TV timeout)
    is_power_play BOOLEAN DEFAULT FALSE,   -- Home or away on PP
    is_empty_net BOOLEAN DEFAULT FALSE,    -- Either team pulled goalie

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT chk_period CHECK (period >= 1 AND period <= 10),
    CONSTRAINT chk_period_second CHECK (period_second >= 0),
    CONSTRAINT chk_game_second CHECK (game_second >= 0),
    CONSTRAINT chk_skater_counts CHECK (
        home_skater_count >= 0 AND home_skater_count <= 6 AND
        away_skater_count >= 0 AND away_skater_count <= 6
    )
);

-- Unique constraint: one snapshot per game-second
CREATE UNIQUE INDEX IF NOT EXISTS idx_second_snapshots_unique
    ON second_snapshots(game_id, game_second);

-- Primary query indexes (T003)
CREATE INDEX IF NOT EXISTS idx_second_snapshots_game
    ON second_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_second_snapshots_situation
    ON second_snapshots(situation_code);
CREATE INDEX IF NOT EXISTS idx_second_snapshots_game_situation
    ON second_snapshots(game_id, situation_code);
CREATE INDEX IF NOT EXISTS idx_second_snapshots_season
    ON second_snapshots(season_id);

-- Player lookup indexes (for matchup queries)
CREATE INDEX IF NOT EXISTS idx_second_snapshots_home_goalie
    ON second_snapshots(home_goalie_id) WHERE home_goalie_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_second_snapshots_away_goalie
    ON second_snapshots(away_goalie_id) WHERE away_goalie_id IS NOT NULL;

-- GIN indexes for array containment queries (find all seconds a player was on ice)
CREATE INDEX IF NOT EXISTS idx_second_snapshots_home_skaters
    ON second_snapshots USING GIN(home_skater_ids);
CREATE INDEX IF NOT EXISTS idx_second_snapshots_away_skaters
    ON second_snapshots USING GIN(away_skater_ids);

-- Comments
COMMENT ON TABLE second_snapshots IS 'Second-by-second game state for analytics (Issue #259)';
COMMENT ON COLUMN second_snapshots.game_second IS 'Total elapsed game seconds (across all periods)';
COMMENT ON COLUMN second_snapshots.period_second IS 'Seconds elapsed in current period (resets each period)';
COMMENT ON COLUMN second_snapshots.situation_code IS 'Manpower situation: 5v5, 5v4, 4v5, 3v3, EN5v4, etc.';
COMMENT ON COLUMN second_snapshots.home_skater_ids IS 'Array of player_ids for home skaters on ice';
COMMENT ON COLUMN second_snapshots.away_skater_ids IS 'Array of player_ids for away skaters on ice';
COMMENT ON COLUMN second_snapshots.is_stoppage IS 'True during stoppages (faceoff pending, TV timeout)';
COMMENT ON COLUMN second_snapshots.is_empty_net IS 'True if either team has pulled their goalie';

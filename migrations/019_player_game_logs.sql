-- Migration: 019_player_game_logs.sql
-- Description: Create player_game_logs table for per-game player statistics
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #124

-- Player game logs table - individual game statistics for each player
CREATE TABLE IF NOT EXISTS player_game_logs (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    game_type VARCHAR(5),  -- R (regular), P (playoff)
    team_abbrev VARCHAR(5),
    opponent_abbrev VARCHAR(5),
    home_road_flag VARCHAR(1),  -- H or R
    game_date DATE,

    -- Common stats for all players
    goals INTEGER,
    assists INTEGER,
    pim INTEGER,
    toi_seconds INTEGER,

    -- Skater-specific stats (null for goalies)
    points INTEGER,
    plus_minus INTEGER,
    shots INTEGER,
    shifts INTEGER,
    power_play_goals INTEGER,
    power_play_points INTEGER,
    shorthanded_goals INTEGER,
    shorthanded_points INTEGER,
    game_winning_goals INTEGER,
    ot_goals INTEGER,

    -- Goalie-specific stats (null for skaters)
    games_started INTEGER,
    decision VARCHAR(2),  -- W, L, O (overtime loss)
    shots_against INTEGER,
    goals_against INTEGER,
    save_pct FLOAT,
    shutouts INTEGER,

    -- Track whether this is a goalie record
    is_goalie BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint per player per game
    UNIQUE(player_id, game_id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_player_game_logs_player_id ON player_game_logs(player_id);
CREATE INDEX IF NOT EXISTS idx_player_game_logs_game_id ON player_game_logs(game_id);
CREATE INDEX IF NOT EXISTS idx_player_game_logs_season_id ON player_game_logs(season_id);
CREATE INDEX IF NOT EXISTS idx_player_game_logs_game_date ON player_game_logs(game_date);
CREATE INDEX IF NOT EXISTS idx_player_game_logs_team ON player_game_logs(team_abbrev);

-- Composite index for player season queries
CREATE INDEX IF NOT EXISTS idx_player_game_logs_player_season
ON player_game_logs(player_id, season_id, game_type);

-- Add comments
COMMENT ON TABLE player_game_logs IS 'Per-game statistics for individual players';
COMMENT ON COLUMN player_game_logs.player_id IS 'NHL player ID';
COMMENT ON COLUMN player_game_logs.game_id IS 'NHL game ID';
COMMENT ON COLUMN player_game_logs.season_id IS 'Season ID (e.g., 20242025)';
COMMENT ON COLUMN player_game_logs.game_type IS 'R for regular season, P for playoffs';
COMMENT ON COLUMN player_game_logs.home_road_flag IS 'H for home, R for road';
COMMENT ON COLUMN player_game_logs.toi_seconds IS 'Time on ice in seconds';
COMMENT ON COLUMN player_game_logs.is_goalie IS 'True if this is a goalie record';
COMMENT ON COLUMN player_game_logs.decision IS 'Goalie decision: W (win), L (loss), O (OT loss)';

-- Add data source for player game logs
INSERT INTO data_sources (name, source_type, base_url, description)
VALUES ('nhl_player_game_log', 'nhl_json', 'https://api-web.nhle.com/v1/player', 'NHL player game log API')
ON CONFLICT (name) DO NOTHING;

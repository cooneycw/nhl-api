-- Migration: 007_games.sql
-- Description: Game data with season-based partitioning
-- Author: Claude Code
-- Date: 2025-12-20

-- Games table: Partitioned by season for performance
CREATE TABLE IF NOT EXISTS games (
    game_id BIGINT NOT NULL,  -- NHL game ID (e.g., 2024020001)
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    game_type VARCHAR(10) NOT NULL,  -- PR=Preseason, R=Regular, P=Playoff, A=All-Star
    game_date DATE NOT NULL,
    game_time TIME WITH TIME ZONE,
    venue_id INTEGER REFERENCES venues(venue_id),
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    period INTEGER,  -- Final period (3, 4 for OT, 5 for SO)
    game_state VARCHAR(20),  -- Scheduled, Live, Final, Postponed, etc.
    detailed_state VARCHAR(50),
    is_overtime BOOLEAN DEFAULT FALSE,
    is_shootout BOOLEAN DEFAULT FALSE,
    game_outcome VARCHAR(20),  -- REG, OT, SO
    attendance INTEGER,
    game_duration_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id)
) PARTITION BY LIST (season_id);

-- Create partitions for target seasons
CREATE TABLE IF NOT EXISTS games_2023 PARTITION OF games FOR VALUES IN (20232024);
CREATE TABLE IF NOT EXISTS games_2024 PARTITION OF games FOR VALUES IN (20242025);

-- Indexes on partitioned table
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_state ON games(game_state);
CREATE INDEX IF NOT EXISTS idx_games_type ON games(game_type);

-- Trigger for updated_at (needs to be on each partition)
CREATE TRIGGER update_games_2023_updated_at
    BEFORE UPDATE ON games_2023
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_games_2024_updated_at
    BEFORE UPDATE ON games_2024
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Game periods: Period-level statistics
CREATE TABLE IF NOT EXISTS game_periods (
    game_id BIGINT NOT NULL,
    season_id INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    period_type VARCHAR(20),  -- REG, OT, SO
    home_goals INTEGER DEFAULT 0,
    away_goals INTEGER DEFAULT 0,
    home_shots INTEGER DEFAULT 0,
    away_shots INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id, period_number),
    FOREIGN KEY (game_id, season_id) REFERENCES games(game_id, season_id)
);

-- Game team stats: Team-level game statistics
CREATE TABLE IF NOT EXISTS game_team_stats (
    game_id BIGINT NOT NULL,
    season_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    is_home BOOLEAN NOT NULL,
    goals INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    pim INTEGER DEFAULT 0,  -- Penalties in minutes
    power_play_goals INTEGER DEFAULT 0,
    power_play_opportunities INTEGER DEFAULT 0,
    faceoff_wins INTEGER DEFAULT 0,
    faceoff_total INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    takeaways INTEGER DEFAULT 0,
    giveaways INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id, team_id),
    FOREIGN KEY (game_id, season_id) REFERENCES games(game_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_gts_team ON game_team_stats(team_id);

COMMENT ON TABLE games IS 'NHL game data partitioned by season';
COMMENT ON TABLE game_periods IS 'Period-by-period game statistics';
COMMENT ON TABLE game_team_stats IS 'Team-level statistics per game';
COMMENT ON COLUMN games.game_id IS 'NHL game ID format: YYYYTTNNNN (year, type, game number)';

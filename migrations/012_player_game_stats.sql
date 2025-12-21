-- Migration: 012_player_game_stats.sql
-- Description: Player-level game statistics (boxscore data)
-- Author: Claude Code
-- Date: 2025-12-21

-- Skater game statistics from boxscore
CREATE TABLE IF NOT EXISTS game_skater_stats (
    game_id BIGINT NOT NULL,
    season_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    position VARCHAR(5),  -- C, L, R, D
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    pim INTEGER DEFAULT 0,  -- Penalties in minutes
    shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    giveaways INTEGER DEFAULT 0,
    takeaways INTEGER DEFAULT 0,
    faceoff_pct DECIMAL(5, 2),  -- Faceoff win percentage
    toi_seconds INTEGER,  -- Time on ice in seconds
    shifts INTEGER DEFAULT 0,
    power_play_goals INTEGER DEFAULT 0,
    shorthanded_goals INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id, player_id),
    FOREIGN KEY (game_id, season_id) REFERENCES games(game_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_gss_player ON game_skater_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_gss_team ON game_skater_stats(team_id);
CREATE INDEX IF NOT EXISTS idx_gss_season ON game_skater_stats(season_id);

-- Goalie game statistics from boxscore
CREATE TABLE IF NOT EXISTS game_goalie_stats (
    game_id BIGINT NOT NULL,
    season_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    saves INTEGER DEFAULT 0,
    shots_against INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    save_pct DECIMAL(5, 4),  -- Save percentage (0.0000 - 1.0000)
    toi_seconds INTEGER,  -- Time on ice in seconds
    even_strength_saves INTEGER DEFAULT 0,
    even_strength_shots INTEGER DEFAULT 0,
    power_play_saves INTEGER DEFAULT 0,
    power_play_shots INTEGER DEFAULT 0,
    shorthanded_saves INTEGER DEFAULT 0,
    shorthanded_shots INTEGER DEFAULT 0,
    is_starter BOOLEAN DEFAULT FALSE,
    decision VARCHAR(5),  -- W, L, OTL, or NULL
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id, player_id),
    FOREIGN KEY (game_id, season_id) REFERENCES games(game_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_ggs_player ON game_goalie_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_ggs_team ON game_goalie_stats(team_id);
CREATE INDEX IF NOT EXISTS idx_ggs_season ON game_goalie_stats(season_id);

-- Comments
COMMENT ON TABLE game_skater_stats IS 'Individual skater statistics per game from boxscore';
COMMENT ON TABLE game_goalie_stats IS 'Individual goalie statistics per game from boxscore';
COMMENT ON COLUMN game_skater_stats.toi_seconds IS 'Time on ice converted from MM:SS to seconds';
COMMENT ON COLUMN game_goalie_stats.decision IS 'Game decision: W (win), L (loss), OTL (overtime loss)';

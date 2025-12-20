-- Migration: 006_player_team_history.sql
-- Description: Player roster tracking over time (trades, signings, etc.)
-- Author: Claude Code
-- Date: 2025-12-20

-- Player team history: Track roster movements
CREATE TABLE IF NOT EXISTS player_team_history (
    history_id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    start_date DATE,
    end_date DATE,  -- NULL if currently on team
    transaction_type VARCHAR(50),  -- Trade, Signing, Waiver, Draft, etc.
    roster_type VARCHAR(20),  -- NHL, AHL, Minors, IR, etc.
    sweater_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pth_player ON player_team_history(player_id);
CREATE INDEX IF NOT EXISTS idx_pth_team ON player_team_history(team_id);
CREATE INDEX IF NOT EXISTS idx_pth_season ON player_team_history(season_id);
CREATE INDEX IF NOT EXISTS idx_pth_dates ON player_team_history(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_pth_player_season ON player_team_history(player_id, season_id);

CREATE TRIGGER update_player_team_history_updated_at
    BEFORE UPDATE ON player_team_history
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Player season summary (denormalized for quick lookups)
CREATE TABLE IF NOT EXISTS player_season_teams (
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    team_ids INTEGER[] NOT NULL,  -- Array of team IDs played for
    games_played INTEGER DEFAULT 0,
    PRIMARY KEY (player_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_pst_season ON player_season_teams(season_id);

COMMENT ON TABLE player_team_history IS 'Historical record of player roster movements';
COMMENT ON TABLE player_season_teams IS 'Summary of teams played for per season (denormalized)';
COMMENT ON COLUMN player_team_history.end_date IS 'NULL indicates player is currently on this team';

-- Migration: 005_players.sql
-- Description: Player biographical and status data
-- Author: Claude Code
-- Date: 2025-12-20

-- Players table: NHL player information
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,  -- NHL API player ID
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    full_name VARCHAR(100) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    birth_date DATE,
    birth_city VARCHAR(100),
    birth_state_province VARCHAR(100),
    birth_country VARCHAR(50),
    nationality VARCHAR(50),
    height_inches INTEGER,  -- Store in inches for consistency
    weight_lbs INTEGER,
    shoots_catches VARCHAR(1),  -- 'L' or 'R'
    primary_position VARCHAR(10),  -- C, LW, RW, D, G
    position_type VARCHAR(20),  -- Forward, Defenseman, Goalie
    roster_status VARCHAR(20),  -- Active, Inactive, Injured, etc.
    current_team_id INTEGER REFERENCES teams(team_id),
    captain BOOLEAN DEFAULT FALSE,
    alternate_captain BOOLEAN DEFAULT FALSE,
    rookie BOOLEAN DEFAULT FALSE,
    nhl_experience INTEGER,  -- Years in NHL
    sweater_number INTEGER,
    headshot_url VARCHAR(500),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_players_full_name ON players(full_name);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(current_team_id);
CREATE INDEX IF NOT EXISTS idx_players_position ON players(primary_position);
CREATE INDEX IF NOT EXISTS idx_players_active ON players(active) WHERE active = TRUE;

CREATE TRIGGER update_players_updated_at
    BEFORE UPDATE ON players
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Player name aliases for cross-source matching
-- Handles cases like "Elias Pettersson" vs "E. Pettersson" vs different spellings
CREATE TABLE IF NOT EXISTS player_aliases (
    alias_id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    alias_name VARCHAR(100) NOT NULL,
    source VARCHAR(50),  -- Which data source uses this alias
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, alias_name, source)
);

CREATE INDEX IF NOT EXISTS idx_player_aliases_name ON player_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_player_aliases_player ON player_aliases(player_id);

COMMENT ON TABLE players IS 'NHL player biographical data and current status';
COMMENT ON TABLE player_aliases IS 'Alternative name spellings for cross-source player matching';
COMMENT ON COLUMN players.shoots_catches IS 'L=Left, R=Right - shoots for skaters, catches for goalies';

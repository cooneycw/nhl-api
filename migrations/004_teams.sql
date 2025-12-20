-- Migration: 004_teams.sql
-- Description: Team data with conference/division/venue relationships
-- Author: Claude Code
-- Date: 2025-12-20

-- Teams table: NHL team information
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,  -- NHL API team ID
    franchise_id INTEGER,
    name VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(10) NOT NULL,
    team_name VARCHAR(50),  -- e.g., "Bruins" without city
    location_name VARCHAR(50),  -- e.g., "Boston"
    division_id INTEGER REFERENCES divisions(division_id),
    conference_id INTEGER REFERENCES conferences(conference_id),
    venue_id INTEGER REFERENCES venues(venue_id),
    first_year_of_play INTEGER,
    official_site_url VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_division ON teams(division_id);
CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference_id);
CREATE INDEX IF NOT EXISTS idx_teams_abbreviation ON teams(abbreviation);
CREATE INDEX IF NOT EXISTS idx_teams_active ON teams(active) WHERE active = TRUE;

CREATE TRIGGER update_teams_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Team season records (for tracking division/conference changes over time)
CREATE TABLE IF NOT EXISTS team_seasons (
    team_id INTEGER REFERENCES teams(team_id),
    season_id INTEGER REFERENCES seasons(season_id),
    division_id INTEGER REFERENCES divisions(division_id),
    conference_id INTEGER REFERENCES conferences(conference_id),
    PRIMARY KEY (team_id, season_id)
);

CREATE INDEX IF NOT EXISTS idx_team_seasons_season ON team_seasons(season_id);

COMMENT ON TABLE teams IS 'NHL team master data with current division/conference assignments';
COMMENT ON TABLE team_seasons IS 'Historical team division/conference assignments by season';

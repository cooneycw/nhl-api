-- Migration 023: HTML Report persistence tables
-- Store parsed HTML report data for cross-source validation

-- Game Summary (GS reports) - scoring and penalty summaries
CREATE TABLE IF NOT EXISTS html_game_summary (
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    away_team_abbrev VARCHAR(3),
    home_team_abbrev VARCHAR(3),
    away_goals INTEGER,
    home_goals INTEGER,
    venue TEXT,
    attendance INTEGER,
    game_date TEXT,
    start_time TEXT,
    end_time TEXT,
    goals JSONB DEFAULT '[]'::jsonb,      -- Array of goal details
    penalties JSONB DEFAULT '[]'::jsonb,   -- Array of penalty details
    referees JSONB DEFAULT '[]'::jsonb,    -- Array of referee names
    linesmen JSONB DEFAULT '[]'::jsonb,    -- Array of linesman names
    parsed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id)
);

-- Event Summary (ES reports) - player stats per game
CREATE TABLE IF NOT EXISTS html_event_summary (
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    away_team_abbrev VARCHAR(3),
    home_team_abbrev VARCHAR(3),
    away_skaters JSONB DEFAULT '[]'::jsonb,   -- Player stats array
    home_skaters JSONB DEFAULT '[]'::jsonb,
    away_goalies JSONB DEFAULT '[]'::jsonb,
    home_goalies JSONB DEFAULT '[]'::jsonb,
    away_totals JSONB,                         -- Team totals
    home_totals JSONB,
    parsed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id)
);

-- Time on Ice (TH/TV reports) - shift-by-shift player TOI
CREATE TABLE IF NOT EXISTS html_time_on_ice (
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    side VARCHAR(4) NOT NULL,  -- 'home' or 'away'
    team_abbrev VARCHAR(3),
    players JSONB DEFAULT '[]'::jsonb,  -- Player TOI details
    parsed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id, side)
);

-- Faceoff Summary (FS reports) - faceoff stats by zone/strength
CREATE TABLE IF NOT EXISTS html_faceoff_summary (
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    away_team_abbrev VARCHAR(3),
    home_team_abbrev VARCHAR(3),
    away_team JSONB,  -- Team faceoff data (by_period, by_strength, players)
    home_team JSONB,
    parsed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id)
);

-- Shot Summary (SS reports) - shot stats by period/situation
CREATE TABLE IF NOT EXISTS html_shot_summary (
    game_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    away_team_abbrev VARCHAR(3),
    home_team_abbrev VARCHAR(3),
    away_periods JSONB DEFAULT '[]'::jsonb,  -- Period shot breakdowns
    home_periods JSONB DEFAULT '[]'::jsonb,
    away_players JSONB DEFAULT '[]'::jsonb,  -- Player shot details
    home_players JSONB DEFAULT '[]'::jsonb,
    parsed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, season_id)
);

-- Add HTML report sources to data_sources if not exists
INSERT INTO data_sources (source_id, name, source_type, base_url, description)
VALUES
    (8, 'html_game_summary', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'NHL HTML Game Summary (GS) reports'),
    (9, 'html_event_summary', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'NHL HTML Event Summary (ES) reports'),
    (10, 'html_time_on_ice', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'NHL HTML Time on Ice (TH/TV) reports'),
    (11, 'html_faceoff_summary', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'NHL HTML Faceoff Summary (FS) reports'),
    (12, 'html_shot_summary', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'NHL HTML Shot Summary (SS) reports')
ON CONFLICT (source_id) DO NOTHING;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_html_game_summary_season ON html_game_summary (season_id);
CREATE INDEX IF NOT EXISTS idx_html_event_summary_season ON html_event_summary (season_id);
CREATE INDEX IF NOT EXISTS idx_html_time_on_ice_season ON html_time_on_ice (season_id);
CREATE INDEX IF NOT EXISTS idx_html_faceoff_summary_season ON html_faceoff_summary (season_id);
CREATE INDEX IF NOT EXISTS idx_html_shot_summary_season ON html_shot_summary (season_id);

COMMENT ON TABLE html_game_summary IS 'Parsed NHL HTML Game Summary (GS) reports with scoring and penalty data';
COMMENT ON TABLE html_event_summary IS 'Parsed NHL HTML Event Summary (ES) reports with per-game player statistics';
COMMENT ON TABLE html_time_on_ice IS 'Parsed NHL HTML Time on Ice (TH/TV) reports with shift data';
COMMENT ON TABLE html_faceoff_summary IS 'Parsed NHL HTML Faceoff Summary (FS) reports with zone/strength breakdowns';
COMMENT ON TABLE html_shot_summary IS 'Parsed NHL HTML Shot Summary (SS) reports with period/situation breakdowns';

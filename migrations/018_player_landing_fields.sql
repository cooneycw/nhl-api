-- Migration: 018_player_landing_fields.sql
-- Description: Add player landing page fields for extended biographical and career data
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #123

-- Add draft information columns
ALTER TABLE players ADD COLUMN IF NOT EXISTS draft_year INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS draft_round INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS draft_pick INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS draft_overall INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS draft_team_abbrev VARCHAR(5);

-- Add hero image URL (already have headshot_url)
ALTER TABLE players ADD COLUMN IF NOT EXISTS hero_image_url VARCHAR(500);

-- Add career NHL totals (regular season)
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_gp INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_goals INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_assists INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_points INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_plus_minus INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_pim INTEGER;

-- Goalie career stats (null for skaters)
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_wins INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_losses INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_ot_losses INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_shutouts INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_gaa FLOAT;
ALTER TABLE players ADD COLUMN IF NOT EXISTS career_save_pct FLOAT;

-- Add special honors
ALTER TABLE players ADD COLUMN IF NOT EXISTS in_top_100_all_time BOOLEAN DEFAULT FALSE;
ALTER TABLE players ADD COLUMN IF NOT EXISTS in_hhof BOOLEAN DEFAULT FALSE;

-- Create index on draft year for historical queries
CREATE INDEX IF NOT EXISTS idx_players_draft_year ON players(draft_year) WHERE draft_year IS NOT NULL;

-- Add comments
COMMENT ON COLUMN players.draft_year IS 'Year player was drafted';
COMMENT ON COLUMN players.draft_round IS 'Draft round (1-7)';
COMMENT ON COLUMN players.draft_pick IS 'Pick number within round';
COMMENT ON COLUMN players.draft_overall IS 'Overall pick number';
COMMENT ON COLUMN players.draft_team_abbrev IS 'Team that drafted the player';
COMMENT ON COLUMN players.hero_image_url IS 'Large action photo from landing page';
COMMENT ON COLUMN players.career_gp IS 'Career NHL regular season games played';
COMMENT ON COLUMN players.career_goals IS 'Career NHL regular season goals';
COMMENT ON COLUMN players.career_assists IS 'Career NHL regular season assists';
COMMENT ON COLUMN players.career_points IS 'Career NHL regular season points';
COMMENT ON COLUMN players.career_plus_minus IS 'Career NHL regular season plus/minus';
COMMENT ON COLUMN players.career_pim IS 'Career NHL regular season penalty minutes';
COMMENT ON COLUMN players.career_wins IS 'Goalie career NHL wins';
COMMENT ON COLUMN players.career_losses IS 'Goalie career NHL losses';
COMMENT ON COLUMN players.career_ot_losses IS 'Goalie career NHL OT losses';
COMMENT ON COLUMN players.career_shutouts IS 'Goalie career NHL shutouts';
COMMENT ON COLUMN players.career_gaa IS 'Goalie career goals against average';
COMMENT ON COLUMN players.career_save_pct IS 'Goalie career save percentage';
COMMENT ON COLUMN players.in_top_100_all_time IS 'Whether player is in NHL Top 100 All-Time list';
COMMENT ON COLUMN players.in_hhof IS 'Whether player is in Hockey Hall of Fame';

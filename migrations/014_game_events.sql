-- Migration: 014_game_events.sql
-- Description: Play-by-play game events for detailed game analysis
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #122

-- Game events table: stores all play-by-play events
CREATE TABLE IF NOT EXISTS game_events (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    event_idx INTEGER NOT NULL,  -- sort_order from API, unique within game

    -- Event identification
    event_type VARCHAR(50) NOT NULL,  -- goal, shot-on-goal, hit, penalty, etc.
    period INTEGER NOT NULL,
    period_type VARCHAR(10),  -- REG, OT, SO
    time_in_period VARCHAR(10),  -- "12:34"
    time_remaining VARCHAR(10),  -- "07:26"

    -- Team attribution
    event_owner_team_id INTEGER,

    -- Primary player (scorer, shooter, hitter, etc.)
    player1_id INTEGER,
    player1_role VARCHAR(30),  -- scorer, shooter, hitter, winner, penaltyOn, etc.

    -- Secondary player (assist1, hittee, loser, drewBy, etc.)
    player2_id INTEGER,
    player2_role VARCHAR(30),

    -- Tertiary player (assist2, goalie, servedBy, etc.)
    player3_id INTEGER,
    player3_role VARCHAR(30),

    -- Goalie in net (for shots/goals)
    goalie_id INTEGER,

    -- Location on ice
    x_coord FLOAT,
    y_coord FLOAT,
    zone VARCHAR(5),  -- O, D, N (offensive, defensive, neutral)

    -- Score state after event
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,

    -- Shot counts after event
    home_sog INTEGER DEFAULT 0,
    away_sog INTEGER DEFAULT 0,

    -- Event details (stored as JSON for flexibility)
    shot_type VARCHAR(50),  -- wrist, slap, snap, backhand, etc.
    description TEXT,
    details JSONB,  -- Additional event-specific data

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one entry per event per game
    UNIQUE(game_id, event_idx)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_game_events_game
    ON game_events(game_id);
CREATE INDEX IF NOT EXISTS idx_game_events_type
    ON game_events(event_type);
CREATE INDEX IF NOT EXISTS idx_game_events_period
    ON game_events(game_id, period);
CREATE INDEX IF NOT EXISTS idx_game_events_player1
    ON game_events(player1_id) WHERE player1_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_game_events_player2
    ON game_events(player2_id) WHERE player2_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_game_events_goalie
    ON game_events(goalie_id) WHERE goalie_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_game_events_team
    ON game_events(event_owner_team_id) WHERE event_owner_team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_game_events_goals
    ON game_events(game_id) WHERE event_type = 'goal';
CREATE INDEX IF NOT EXISTS idx_game_events_shots
    ON game_events(game_id) WHERE event_type IN ('shot-on-goal', 'missed-shot', 'blocked-shot', 'goal');

COMMENT ON TABLE game_events IS 'Play-by-play events from NHL games for detailed game analysis';
COMMENT ON COLUMN game_events.event_idx IS 'Sort order from API, unique event identifier within a game';
COMMENT ON COLUMN game_events.player1_id IS 'Primary player: scorer, shooter, hitter, winner, penaltyOn';
COMMENT ON COLUMN game_events.player2_id IS 'Secondary player: assist1, hittee, loser, drewBy';
COMMENT ON COLUMN game_events.player3_id IS 'Tertiary player: assist2, blocker, servedBy';
COMMENT ON COLUMN game_events.details IS 'Event-specific details as JSON (penalty duration, highlight URL, etc.)';

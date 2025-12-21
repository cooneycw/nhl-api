-- Migration: 014_shift_charts.sql
-- Description: Game shift-by-shift player tracking data from NHL Stats API
-- Author: Claude Code
-- Date: 2025-12-21

-- Game shifts: Individual player shift records
CREATE TABLE IF NOT EXISTS game_shifts (
    shift_id BIGINT PRIMARY KEY,
    game_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    team_id INTEGER NOT NULL,
    period INTEGER NOT NULL,
    shift_number INTEGER NOT NULL,
    start_time VARCHAR(10) NOT NULL,  -- "MM:SS" format
    end_time VARCHAR(10) NOT NULL,    -- "MM:SS" format
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    is_goal_event BOOLEAN DEFAULT FALSE,
    event_description VARCHAR(50),  -- e.g., "EVG", "PPG" for goal events
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Note: game_id foreign key not enforced since games table uses composite key
-- and we want flexibility to load shifts before games are loaded

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_game_shifts_game ON game_shifts(game_id);
CREATE INDEX IF NOT EXISTS idx_game_shifts_player ON game_shifts(player_id);
CREATE INDEX IF NOT EXISTS idx_game_shifts_team_period ON game_shifts(team_id, period);
CREATE INDEX IF NOT EXISTS idx_game_shifts_game_player ON game_shifts(game_id, player_id);

-- Comments
COMMENT ON TABLE game_shifts IS 'Player shift-by-shift data from NHL Stats API (/shiftcharts endpoint)';
COMMENT ON COLUMN game_shifts.shift_id IS 'Unique shift identifier from NHL API';
COMMENT ON COLUMN game_shifts.start_time IS 'Shift start time in MM:SS format (game clock)';
COMMENT ON COLUMN game_shifts.end_time IS 'Shift end time in MM:SS format (game clock)';
COMMENT ON COLUMN game_shifts.duration_seconds IS 'Shift duration converted from MM:SS to seconds';
COMMENT ON COLUMN game_shifts.is_goal_event IS 'True if this record represents a goal event (typeCode=505)';
COMMENT ON COLUMN game_shifts.event_description IS 'Goal type (EVG, PPG, SHG) for goal events';

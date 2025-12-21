-- Migration: 017_add_20252026_season.sql
-- Description: Add 2025-2026 season and set as current
-- Author: Claude Code
-- Date: 2025-12-21

-- Mark previous season as not current
UPDATE seasons SET is_current = FALSE WHERE is_current = TRUE;

-- Add 2025-2026 season
INSERT INTO seasons (season_id, start_year, end_year, is_current)
VALUES (20252026, 2025, 2026, TRUE)
ON CONFLICT (season_id) DO UPDATE SET is_current = TRUE;

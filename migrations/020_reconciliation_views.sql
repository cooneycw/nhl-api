-- Migration: 020_reconciliation_views.sql
-- Description: Materialized views for reconciliation dashboard (cross-source data validation)
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #153

-- ============================================================================
-- MATERIALIZED VIEW: mv_reconciliation_summary
-- Purpose: Aggregated reconciliation statistics per season for dashboard
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_reconciliation_summary AS
WITH game_goal_check AS (
    -- Compare PBP goals vs boxscore goals per team
    SELECT
        ge.game_id,
        g.season_id,
        ge.event_owner_team_id AS team_id,
        COUNT(*) AS pbp_goals,
        gts.goals AS boxscore_goals,
        COUNT(*) = COALESCE(gts.goals, 0) AS goals_match
    FROM game_events ge
    JOIN games g ON ge.game_id = g.game_id
    LEFT JOIN game_team_stats gts ON ge.game_id = gts.game_id
        AND ge.event_owner_team_id = gts.team_id
        AND g.season_id = gts.season_id
    WHERE ge.event_type = 'goal'
      AND ge.event_owner_team_id IS NOT NULL
    GROUP BY ge.game_id, g.season_id, ge.event_owner_team_id, gts.goals
),
toi_check AS (
    -- Compare shift TOI vs boxscore TOI per player (5-second tolerance)
    SELECT
        gss.game_id,
        gss.season_id,
        gss.player_id,
        gss.toi_seconds AS boxscore_toi,
        COALESCE(SUM(gs.duration_seconds), 0) AS shift_toi,
        ABS(COALESCE(gss.toi_seconds, 0) - COALESCE(SUM(gs.duration_seconds), 0)) <= 5 AS toi_match
    FROM game_skater_stats gss
    LEFT JOIN game_shifts gs ON gss.game_id = gs.game_id
        AND gss.player_id = gs.player_id
    GROUP BY gss.game_id, gss.season_id, gss.player_id, gss.toi_seconds
),
penalty_check AS (
    -- Compare PBP penalties vs boxscore PIM consistency
    -- Both should have penalties or both should have none
    SELECT
        g.game_id,
        g.season_id,
        gts.team_id,
        COUNT(ge.id) AS pbp_penalties,
        gts.pim AS boxscore_pim,
        -- Match if both have penalties or both have none
        (COUNT(ge.id) > 0 AND COALESCE(gts.pim, 0) > 0) OR
        (COUNT(ge.id) = 0 AND COALESCE(gts.pim, 0) = 0) AS penalty_match
    FROM games g
    JOIN game_team_stats gts ON g.game_id = gts.game_id AND g.season_id = gts.season_id
    LEFT JOIN game_events ge ON g.game_id = ge.game_id
        AND ge.event_type = 'penalty'
        AND ge.event_owner_team_id = gts.team_id
    GROUP BY g.game_id, g.season_id, gts.team_id, gts.pim
),
shot_check AS (
    -- Compare PBP shots (including goals) vs boxscore shots per team
    SELECT
        g.game_id,
        g.season_id,
        gts.team_id,
        COUNT(CASE WHEN ge.event_type IN ('shot-on-goal', 'goal') THEN 1 END) AS pbp_shots,
        gts.shots AS boxscore_shots,
        -- Shots should match within reasonable tolerance
        ABS(COUNT(CASE WHEN ge.event_type IN ('shot-on-goal', 'goal') THEN 1 END)
            - COALESCE(gts.shots, 0)) <= 2 AS shot_match
    FROM games g
    JOIN game_team_stats gts ON g.game_id = gts.game_id AND g.season_id = gts.season_id
    LEFT JOIN game_events ge ON g.game_id = ge.game_id
        AND ge.event_owner_team_id = gts.team_id
    GROUP BY g.game_id, g.season_id, gts.team_id, gts.shots
)
SELECT
    COALESCE(ggc.season_id, tc.season_id, pc.season_id, sc.season_id) AS season_id,
    COUNT(DISTINCT COALESCE(ggc.game_id, tc.game_id, pc.game_id, sc.game_id)) AS total_games,
    -- Goal discrepancy stats
    COUNT(DISTINCT CASE WHEN ggc.goals_match = FALSE THEN ggc.game_id END) AS games_goal_issues,
    COUNT(CASE WHEN ggc.goals_match = TRUE THEN 1 END) AS goal_checks_passed,
    COUNT(CASE WHEN ggc.goals_match = FALSE THEN 1 END) AS goal_checks_failed,
    -- TOI discrepancy stats
    COUNT(DISTINCT CASE WHEN tc.toi_match = FALSE THEN tc.game_id END) AS games_toi_issues,
    COUNT(CASE WHEN tc.toi_match = TRUE THEN 1 END) AS toi_checks_passed,
    COUNT(CASE WHEN tc.toi_match = FALSE THEN 1 END) AS toi_checks_failed,
    -- Penalty discrepancy stats
    COUNT(DISTINCT CASE WHEN pc.penalty_match = FALSE THEN pc.game_id END) AS games_penalty_issues,
    COUNT(CASE WHEN pc.penalty_match = TRUE THEN 1 END) AS penalty_checks_passed,
    COUNT(CASE WHEN pc.penalty_match = FALSE THEN 1 END) AS penalty_checks_failed,
    -- Shot discrepancy stats
    COUNT(DISTINCT CASE WHEN sc.shot_match = FALSE THEN sc.game_id END) AS games_shot_issues,
    COUNT(CASE WHEN sc.shot_match = TRUE THEN 1 END) AS shot_checks_passed,
    COUNT(CASE WHEN sc.shot_match = FALSE THEN 1 END) AS shot_checks_failed,
    -- Refresh timestamp
    CURRENT_TIMESTAMP AS refreshed_at
FROM game_goal_check ggc
FULL OUTER JOIN toi_check tc ON ggc.game_id = tc.game_id AND ggc.season_id = tc.season_id
FULL OUTER JOIN penalty_check pc ON COALESCE(ggc.game_id, tc.game_id) = pc.game_id
    AND COALESCE(ggc.season_id, tc.season_id) = pc.season_id
FULL OUTER JOIN shot_check sc ON COALESCE(ggc.game_id, tc.game_id, pc.game_id) = sc.game_id
    AND COALESCE(ggc.season_id, tc.season_id, pc.season_id) = sc.season_id
WHERE COALESCE(ggc.season_id, tc.season_id, pc.season_id, sc.season_id) IS NOT NULL
GROUP BY COALESCE(ggc.season_id, tc.season_id, pc.season_id, sc.season_id)
WITH DATA;

-- Unique index required for CONCURRENT refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_reconciliation_summary_pk
    ON mv_reconciliation_summary(season_id);


-- ============================================================================
-- MATERIALIZED VIEW: mv_reconciliation_game_detail
-- Purpose: Per-game reconciliation check results for game list and detail views
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_reconciliation_game_detail AS
WITH goal_discrepancies AS (
    SELECT
        ge.game_id,
        g.season_id,
        ge.event_owner_team_id AS team_id,
        'goal_count' AS check_type,
        COUNT(*) AS pbp_value,
        gts.goals AS boxscore_value,
        COUNT(*) = COALESCE(gts.goals, 0) AS passed,
        ABS(COUNT(*) - COALESCE(gts.goals, 0)) AS difference
    FROM game_events ge
    JOIN games g ON ge.game_id = g.game_id
    LEFT JOIN game_team_stats gts ON ge.game_id = gts.game_id
        AND ge.event_owner_team_id = gts.team_id
        AND g.season_id = gts.season_id
    WHERE ge.event_type = 'goal'
      AND ge.event_owner_team_id IS NOT NULL
    GROUP BY ge.game_id, g.season_id, ge.event_owner_team_id, gts.goals
),
toi_discrepancies AS (
    SELECT
        gss.game_id,
        gss.season_id,
        gss.player_id AS entity_id,
        'toi_seconds' AS check_type,
        COALESCE(SUM(gs.duration_seconds), 0) AS shift_value,
        gss.toi_seconds AS boxscore_value,
        ABS(COALESCE(gss.toi_seconds, 0) - COALESCE(SUM(gs.duration_seconds), 0)) <= 5 AS passed,
        ABS(COALESCE(gss.toi_seconds, 0) - COALESCE(SUM(gs.duration_seconds), 0)) AS difference
    FROM game_skater_stats gss
    LEFT JOIN game_shifts gs ON gss.game_id = gs.game_id AND gss.player_id = gs.player_id
    GROUP BY gss.game_id, gss.season_id, gss.player_id, gss.toi_seconds
),
shot_discrepancies AS (
    SELECT
        g.game_id,
        g.season_id,
        gts.team_id,
        'shot_count' AS check_type,
        COUNT(CASE WHEN ge.event_type IN ('shot-on-goal', 'goal') THEN 1 END) AS pbp_value,
        gts.shots AS boxscore_value,
        ABS(COUNT(CASE WHEN ge.event_type IN ('shot-on-goal', 'goal') THEN 1 END)
            - COALESCE(gts.shots, 0)) <= 2 AS passed,
        ABS(COUNT(CASE WHEN ge.event_type IN ('shot-on-goal', 'goal') THEN 1 END)
            - COALESCE(gts.shots, 0)) AS difference
    FROM games g
    JOIN game_team_stats gts ON g.game_id = gts.game_id AND g.season_id = gts.season_id
    LEFT JOIN game_events ge ON g.game_id = ge.game_id
        AND ge.event_owner_team_id = gts.team_id
    GROUP BY g.game_id, g.season_id, gts.team_id, gts.shots
)
SELECT
    g.game_id,
    g.season_id,
    g.game_date,
    ht.abbreviation AS home_team,
    at.abbreviation AS away_team,
    -- Aggregate check counts
    (SELECT COUNT(*) FROM goal_discrepancies gd WHERE gd.game_id = g.game_id AND gd.passed = TRUE)
        + (SELECT COUNT(*) FROM toi_discrepancies td WHERE td.game_id = g.game_id AND td.passed = TRUE)
        + (SELECT COUNT(*) FROM shot_discrepancies sd WHERE sd.game_id = g.game_id AND sd.passed = TRUE)
        AS checks_passed,
    (SELECT COUNT(*) FROM goal_discrepancies gd WHERE gd.game_id = g.game_id AND gd.passed = FALSE)
        + (SELECT COUNT(*) FROM toi_discrepancies td WHERE td.game_id = g.game_id AND td.passed = FALSE)
        + (SELECT COUNT(*) FROM shot_discrepancies sd WHERE sd.game_id = g.game_id AND sd.passed = FALSE)
        AS checks_failed,
    -- Has any discrepancy
    EXISTS (SELECT 1 FROM goal_discrepancies gd WHERE gd.game_id = g.game_id AND gd.passed = FALSE)
        OR EXISTS (SELECT 1 FROM toi_discrepancies td WHERE td.game_id = g.game_id AND td.passed = FALSE)
        OR EXISTS (SELECT 1 FROM shot_discrepancies sd WHERE sd.game_id = g.game_id AND sd.passed = FALSE)
        AS has_discrepancy,
    -- Discrepancy types present
    EXISTS (SELECT 1 FROM goal_discrepancies gd WHERE gd.game_id = g.game_id AND gd.passed = FALSE) AS has_goal_issue,
    EXISTS (SELECT 1 FROM toi_discrepancies td WHERE td.game_id = g.game_id AND td.passed = FALSE) AS has_toi_issue,
    EXISTS (SELECT 1 FROM shot_discrepancies sd WHERE sd.game_id = g.game_id AND sd.passed = FALSE) AS has_shot_issue,
    CURRENT_TIMESTAMP AS refreshed_at
FROM games g
JOIN teams ht ON g.home_team_id = ht.team_id
JOIN teams at ON g.away_team_id = at.team_id
WHERE g.game_state = 'Final'
WITH DATA;

-- Indexes for efficient queries
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_recon_game_pk
    ON mv_reconciliation_game_detail(game_id, season_id);
CREATE INDEX IF NOT EXISTS idx_mv_recon_game_season
    ON mv_reconciliation_game_detail(season_id);
CREATE INDEX IF NOT EXISTS idx_mv_recon_game_has_issue
    ON mv_reconciliation_game_detail(season_id, has_discrepancy)
    WHERE has_discrepancy = TRUE;
CREATE INDEX IF NOT EXISTS idx_mv_recon_game_goal_issue
    ON mv_reconciliation_game_detail(season_id)
    WHERE has_goal_issue = TRUE;
CREATE INDEX IF NOT EXISTS idx_mv_recon_game_toi_issue
    ON mv_reconciliation_game_detail(season_id)
    WHERE has_toi_issue = TRUE;
CREATE INDEX IF NOT EXISTS idx_mv_recon_game_shot_issue
    ON mv_reconciliation_game_detail(season_id)
    WHERE has_shot_issue = TRUE;


-- ============================================================================
-- UPDATE REFRESH FUNCTIONS
-- Purpose: Add reconciliation views to the refresh functions
-- ============================================================================

-- Drop and recreate the refresh_viewer_views function to include new views
CREATE OR REPLACE FUNCTION refresh_viewer_views(concurrent BOOLEAN DEFAULT TRUE)
RETURNS TABLE(view_name TEXT, refreshed_at TIMESTAMP WITH TIME ZONE, duration_ms BIGINT) AS $$
DECLARE
    start_time TIMESTAMP WITH TIME ZONE;
    end_time TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Batch stats
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_download_batch_stats;
    ELSE
        REFRESH MATERIALIZED VIEW mv_download_batch_stats;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_download_batch_stats';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;

    -- Source health
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_health;
    ELSE
        REFRESH MATERIALIZED VIEW mv_source_health;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_source_health';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;

    -- Player summary
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_summary;
    ELSE
        REFRESH MATERIALIZED VIEW mv_player_summary;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_player_summary';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;

    -- Game summary
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_game_summary;
    ELSE
        REFRESH MATERIALIZED VIEW mv_game_summary;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_game_summary';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;

    -- Reconciliation summary
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_summary;
    ELSE
        REFRESH MATERIALIZED VIEW mv_reconciliation_summary;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_reconciliation_summary';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;

    -- Reconciliation game detail
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_game_detail;
    ELSE
        REFRESH MATERIALIZED VIEW mv_reconciliation_game_detail;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_reconciliation_game_detail';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Update refresh_viewer_view function to include new views
CREATE OR REPLACE FUNCTION refresh_viewer_view(
    p_view_name TEXT,
    concurrent BOOLEAN DEFAULT TRUE
)
RETURNS TIMESTAMP WITH TIME ZONE AS $$
DECLARE
    refreshed TIMESTAMP WITH TIME ZONE;
BEGIN
    CASE p_view_name
        WHEN 'mv_download_batch_stats' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_download_batch_stats;
            ELSE
                REFRESH MATERIALIZED VIEW mv_download_batch_stats;
            END IF;
        WHEN 'mv_source_health' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_source_health;
            ELSE
                REFRESH MATERIALIZED VIEW mv_source_health;
            END IF;
        WHEN 'mv_player_summary' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_summary;
            ELSE
                REFRESH MATERIALIZED VIEW mv_player_summary;
            END IF;
        WHEN 'mv_game_summary' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_game_summary;
            ELSE
                REFRESH MATERIALIZED VIEW mv_game_summary;
            END IF;
        WHEN 'mv_reconciliation_summary' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_summary;
            ELSE
                REFRESH MATERIALIZED VIEW mv_reconciliation_summary;
            END IF;
        WHEN 'mv_reconciliation_game_detail' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_game_detail;
            ELSE
                REFRESH MATERIALIZED VIEW mv_reconciliation_game_detail;
            END IF;
        ELSE
            RAISE EXCEPTION 'Unknown view: %', p_view_name;
    END CASE;

    refreshed := CURRENT_TIMESTAMP;
    RETURN refreshed;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON MATERIALIZED VIEW mv_reconciliation_summary IS
    'Aggregated reconciliation statistics per season for dashboard overview';
COMMENT ON MATERIALIZED VIEW mv_reconciliation_game_detail IS
    'Per-game reconciliation check results for discrepancy investigation';
COMMENT ON FUNCTION refresh_viewer_views IS
    'Refresh all viewer materialized views including reconciliation (use concurrent=TRUE for zero-downtime)';

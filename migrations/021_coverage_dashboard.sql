-- Migration: 021_coverage_dashboard.sql
-- Description: Materialized view for data coverage "gas tank" dashboard
-- Author: Claude Code
-- Date: 2025-12-21
-- Issue: #176 (part of #174)

-- ============================================================================
-- MATERIALIZED VIEW: mv_data_coverage
-- Purpose: Aggregated data coverage statistics per season for "gas tank" dashboard
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_data_coverage AS
WITH
season_base AS (
    SELECT
        s.season_id,
        CAST(s.start_year AS TEXT) || '-' || CAST(s.end_year AS TEXT) AS season_label,
        COALESCE(s.games_scheduled, 0) AS games_scheduled,
        s.is_current
    FROM seasons s
),
game_counts AS (
    -- Count of final games per season (game_state can be 'FINAL', 'Final', etc.)
    SELECT
        season_id,
        COUNT(*) FILTER (WHERE UPPER(game_state) = 'FINAL') AS games_final,
        COUNT(*) AS games_total
    FROM games
    GROUP BY season_id
),
boxscore_counts AS (
    -- Games that have team stats (boxscore data)
    SELECT
        g.season_id,
        COUNT(DISTINCT gts.game_id) AS boxscore_actual
    FROM games g
    LEFT JOIN game_team_stats gts ON g.game_id = gts.game_id AND g.season_id = gts.season_id
    WHERE UPPER(g.game_state) = 'FINAL'
    GROUP BY g.season_id
),
pbp_counts AS (
    -- Games that have play-by-play events
    SELECT
        g.season_id,
        COUNT(DISTINCT ge.game_id) AS pbp_actual
    FROM games g
    LEFT JOIN game_events ge ON g.game_id = ge.game_id
    WHERE UPPER(g.game_state) = 'FINAL'
    GROUP BY g.season_id
),
shifts_counts AS (
    -- Games that have shift chart data
    SELECT
        g.season_id,
        COUNT(DISTINCT gs.game_id) AS shifts_actual
    FROM games g
    LEFT JOIN game_shifts gs ON g.game_id = gs.game_id
    WHERE UPPER(g.game_state) = 'FINAL'
    GROUP BY g.season_id
),
roster_player_counts AS (
    -- Distinct players on rosters per season (expected players)
    SELECT
        tr.season_id,
        COUNT(DISTINCT tr.player_id) AS players_on_roster
    FROM team_rosters tr
    GROUP BY tr.season_id
),
player_landing_counts AS (
    -- Players with landing page data (have bio info populated)
    -- A player has landing data if they have height/weight/birth_date filled in
    SELECT
        tr.season_id,
        COUNT(DISTINCT CASE
            WHEN p.height_inches IS NOT NULL
             AND p.birth_date IS NOT NULL
            THEN tr.player_id
        END) AS players_with_landing
    FROM team_rosters tr
    JOIN players p ON tr.player_id = p.player_id
    GROUP BY tr.season_id
),
game_log_counts AS (
    -- Player game log statistics
    SELECT
        season_id,
        COUNT(*) AS game_logs_total,
        COUNT(DISTINCT player_id) AS players_with_game_logs
    FROM player_game_logs
    GROUP BY season_id
),
html_download_counts AS (
    -- Games with HTML report downloads (any html_* source)
    -- Uses download_progress to track successful HTML downloads
    SELECT
        dp.season_id,
        COUNT(DISTINCT dp.item_key) AS html_actual
    FROM download_progress dp
    JOIN data_sources ds ON dp.source_id = ds.source_id
    WHERE ds.name LIKE 'html_%'
      AND dp.status = 'success'
    GROUP BY dp.season_id
)
SELECT
    sb.season_id,
    sb.season_label,
    sb.is_current,
    -- Games
    sb.games_scheduled,
    COALESCE(gc.games_final, 0) AS games_final,
    COALESCE(gc.games_total, 0) AS games_total,
    -- Boxscore coverage
    COALESCE(gc.games_final, 0) AS boxscore_expected,
    COALESCE(bc.boxscore_actual, 0) AS boxscore_actual,
    CASE
        WHEN COALESCE(gc.games_final, 0) > 0
        THEN ROUND((COALESCE(bc.boxscore_actual, 0)::DECIMAL / gc.games_final) * 100, 1)
        ELSE 0
    END AS boxscore_pct,
    -- Play-by-play coverage
    COALESCE(gc.games_final, 0) AS pbp_expected,
    COALESCE(pc.pbp_actual, 0) AS pbp_actual,
    CASE
        WHEN COALESCE(gc.games_final, 0) > 0
        THEN ROUND((COALESCE(pc.pbp_actual, 0)::DECIMAL / gc.games_final) * 100, 1)
        ELSE 0
    END AS pbp_pct,
    -- Shift charts coverage
    COALESCE(gc.games_final, 0) AS shifts_expected,
    COALESCE(sc.shifts_actual, 0) AS shifts_actual,
    CASE
        WHEN COALESCE(gc.games_final, 0) > 0
        THEN ROUND((COALESCE(sc.shifts_actual, 0)::DECIMAL / gc.games_final) * 100, 1)
        ELSE 0
    END AS shifts_pct,
    -- Player landing coverage
    COALESCE(rpc.players_on_roster, 0) AS players_expected,
    COALESCE(plc.players_with_landing, 0) AS players_actual,
    CASE
        WHEN COALESCE(rpc.players_on_roster, 0) > 0
        THEN ROUND((COALESCE(plc.players_with_landing, 0)::DECIMAL / rpc.players_on_roster) * 100, 1)
        ELSE 0
    END AS players_pct,
    -- HTML reports coverage
    COALESCE(gc.games_final, 0) AS html_expected,
    COALESCE(hdc.html_actual, 0) AS html_actual,
    CASE
        WHEN COALESCE(gc.games_final, 0) > 0
        THEN ROUND((COALESCE(hdc.html_actual, 0)::DECIMAL / gc.games_final) * 100, 1)
        ELSE 0
    END AS html_pct,
    -- Game logs
    COALESCE(glc.game_logs_total, 0) AS game_logs_total,
    COALESCE(glc.players_with_game_logs, 0) AS players_with_game_logs,
    -- Refresh timestamp
    CURRENT_TIMESTAMP AS refreshed_at
FROM season_base sb
LEFT JOIN game_counts gc ON sb.season_id = gc.season_id
LEFT JOIN boxscore_counts bc ON sb.season_id = bc.season_id
LEFT JOIN pbp_counts pc ON sb.season_id = pc.season_id
LEFT JOIN shifts_counts sc ON sb.season_id = sc.season_id
LEFT JOIN roster_player_counts rpc ON sb.season_id = rpc.season_id
LEFT JOIN player_landing_counts plc ON sb.season_id = plc.season_id
LEFT JOIN game_log_counts glc ON sb.season_id = glc.season_id
LEFT JOIN html_download_counts hdc ON sb.season_id = hdc.season_id
WITH DATA;

-- Unique index required for CONCURRENT refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_data_coverage_pk
    ON mv_data_coverage(season_id);

-- Index for filtering by current season
CREATE INDEX IF NOT EXISTS idx_mv_data_coverage_current
    ON mv_data_coverage(is_current)
    WHERE is_current = TRUE;


-- ============================================================================
-- UPDATE REFRESH FUNCTIONS
-- Purpose: Add mv_data_coverage to the refresh functions
-- ============================================================================

-- Drop and recreate the refresh_viewer_views function to include new view
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

    -- Data coverage
    start_time := clock_timestamp();
    IF concurrent THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_data_coverage;
    ELSE
        REFRESH MATERIALIZED VIEW mv_data_coverage;
    END IF;
    end_time := clock_timestamp();
    view_name := 'mv_data_coverage';
    refreshed_at := end_time;
    duration_ms := EXTRACT(MILLISECONDS FROM (end_time - start_time))::BIGINT;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Update refresh_viewer_view function to include new view
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
        WHEN 'mv_data_coverage' THEN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_data_coverage;
            ELSE
                REFRESH MATERIALIZED VIEW mv_data_coverage;
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
COMMENT ON MATERIALIZED VIEW mv_data_coverage IS
    'Data coverage statistics per season for "gas tank" dashboard visualization';

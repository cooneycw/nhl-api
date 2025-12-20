-- Migration: 010_viewer_views.sql
-- Description: Materialized views and indexes optimized for the Data Viewer
-- Author: Claude Code
-- Date: 2025-12-20
-- Issue: #41 (Database Views for Viewer)

-- ============================================================================
-- MATERIALIZED VIEW: mv_download_batch_stats
-- Purpose: Aggregated batch progress, success/failure counts for dashboard
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_download_batch_stats AS
SELECT
    ib.batch_id,
    ib.source_id,
    ds.name AS source_name,
    ds.source_type,
    ib.season_id,
    CAST(s.start_year AS TEXT) || CAST(s.end_year AS TEXT) AS season_name,
    ib.status,
    ib.started_at,
    ib.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(ib.completed_at, CURRENT_TIMESTAMP) - ib.started_at)) AS duration_seconds,
    ib.items_total,
    ib.items_success,
    ib.items_failed,
    ib.items_skipped,
    CASE
        WHEN ib.items_total > 0
        THEN ROUND((ib.items_success::DECIMAL / ib.items_total) * 100, 2)
        ELSE 0
    END AS success_rate,
    CASE
        WHEN ib.items_total > 0
        THEN ROUND(((ib.items_success + ib.items_skipped)::DECIMAL / ib.items_total) * 100, 2)
        ELSE 0
    END AS completion_rate,
    ib.error_message,
    ib.metadata
FROM import_batches ib
JOIN data_sources ds ON ib.source_id = ds.source_id
LEFT JOIN seasons s ON ib.season_id = s.season_id
WITH DATA;

-- Unique index required for CONCURRENT refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_batch_stats_pk
    ON mv_download_batch_stats(batch_id);
CREATE INDEX IF NOT EXISTS idx_mv_batch_stats_source
    ON mv_download_batch_stats(source_id);
CREATE INDEX IF NOT EXISTS idx_mv_batch_stats_status
    ON mv_download_batch_stats(status);
CREATE INDEX IF NOT EXISTS idx_mv_batch_stats_started
    ON mv_download_batch_stats(started_at DESC);
-- Partial index for active batches (dashboard priority)
CREATE INDEX IF NOT EXISTS idx_mv_batch_stats_running
    ON mv_download_batch_stats(source_id, started_at DESC)
    WHERE status = 'running';

-- ============================================================================
-- MATERIALIZED VIEW: mv_source_health
-- Purpose: Per-source status summary for health monitoring grid
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_source_health AS
SELECT
    ds.source_id,
    ds.name AS source_name,
    ds.source_type,
    ds.is_active,
    ds.rate_limit_ms,
    ds.max_concurrent,
    -- Latest batch info
    latest.batch_id AS latest_batch_id,
    latest.status AS latest_status,
    latest.started_at AS latest_started_at,
    latest.completed_at AS latest_completed_at,
    -- Aggregated stats (last 24 hours)
    COALESCE(stats_24h.batches_count, 0) AS batches_last_24h,
    COALESCE(stats_24h.total_items, 0) AS items_last_24h,
    COALESCE(stats_24h.success_items, 0) AS success_last_24h,
    COALESCE(stats_24h.failed_items, 0) AS failed_last_24h,
    CASE
        WHEN COALESCE(stats_24h.total_items, 0) > 0
        THEN ROUND((stats_24h.success_items::DECIMAL / stats_24h.total_items) * 100, 2)
        ELSE NULL
    END AS success_rate_24h,
    -- All-time stats
    COALESCE(stats_all.total_batches, 0) AS total_batches,
    COALESCE(stats_all.total_items, 0) AS total_items_all_time,
    COALESCE(stats_all.success_items, 0) AS success_items_all_time,
    -- Health status derived
    CASE
        WHEN NOT ds.is_active THEN 'inactive'
        WHEN latest.status = 'running' THEN 'running'
        WHEN latest.status = 'failed' THEN 'error'
        WHEN COALESCE(stats_24h.failed_items, 0) > COALESCE(stats_24h.success_items, 0) THEN 'degraded'
        WHEN latest.status = 'completed' THEN 'healthy'
        ELSE 'unknown'
    END AS health_status,
    CURRENT_TIMESTAMP AS refreshed_at
FROM data_sources ds
LEFT JOIN LATERAL (
    SELECT batch_id, status, started_at, completed_at
    FROM import_batches
    WHERE source_id = ds.source_id
    ORDER BY started_at DESC
    LIMIT 1
) latest ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS batches_count,
        SUM(items_total) AS total_items,
        SUM(items_success) AS success_items,
        SUM(items_failed) AS failed_items
    FROM import_batches
    WHERE source_id = ds.source_id
      AND started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
) stats_24h ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS total_batches,
        SUM(items_total) AS total_items,
        SUM(items_success) AS success_items
    FROM import_batches
    WHERE source_id = ds.source_id
) stats_all ON TRUE
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_source_health_pk
    ON mv_source_health(source_id);
CREATE INDEX IF NOT EXISTS idx_mv_source_health_status
    ON mv_source_health(health_status);
CREATE INDEX IF NOT EXISTS idx_mv_source_health_type
    ON mv_source_health(source_type);

-- ============================================================================
-- MATERIALIZED VIEW: mv_player_summary
-- Purpose: Player info with current team for explorer/search
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_player_summary AS
SELECT
    p.player_id,
    p.first_name,
    p.last_name,
    p.full_name,
    p.birth_date,
    EXTRACT(YEAR FROM AGE(p.birth_date))::INTEGER AS age,
    p.birth_country,
    p.nationality,
    p.height_inches,
    CASE
        WHEN p.height_inches IS NOT NULL
        THEN (p.height_inches / 12) || '''' || (p.height_inches % 12) || '"'
        ELSE NULL
    END AS height_display,
    p.weight_lbs,
    p.shoots_catches,
    p.primary_position,
    p.position_type,
    p.roster_status,
    p.current_team_id,
    t.name AS team_name,
    t.abbreviation AS team_abbreviation,
    d.name AS division_name,
    c.name AS conference_name,
    p.captain,
    p.alternate_captain,
    p.rookie,
    p.nhl_experience,
    p.sweater_number,
    p.headshot_url,
    p.active,
    p.updated_at
FROM players p
LEFT JOIN teams t ON p.current_team_id = t.team_id
LEFT JOIN divisions d ON t.division_id = d.division_id
LEFT JOIN conferences c ON t.conference_id = c.conference_id
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_player_summary_pk
    ON mv_player_summary(player_id);
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_name
    ON mv_player_summary(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_full_name
    ON mv_player_summary(full_name);
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_team
    ON mv_player_summary(current_team_id);
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_position
    ON mv_player_summary(primary_position);
-- Partial index for active players (most common query)
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_active
    ON mv_player_summary(last_name, first_name)
    WHERE active = TRUE;
-- Text search support
CREATE INDEX IF NOT EXISTS idx_mv_player_summary_search
    ON mv_player_summary USING GIN (to_tsvector('english', full_name));

-- ============================================================================
-- MATERIALIZED VIEW: mv_game_summary
-- Purpose: Game info with teams and venue for explorer
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_game_summary AS
SELECT
    g.game_id,
    g.season_id,
    CAST(s.start_year AS TEXT) || CAST(s.end_year AS TEXT) AS season_name,
    g.game_type,
    CASE g.game_type
        WHEN 'PR' THEN 'Preseason'
        WHEN 'R' THEN 'Regular Season'
        WHEN 'P' THEN 'Playoffs'
        WHEN 'A' THEN 'All-Star'
        ELSE g.game_type
    END AS game_type_name,
    g.game_date,
    g.game_time,
    g.venue_id,
    v.name AS venue_name,
    v.city AS venue_city,
    -- Home team
    g.home_team_id,
    ht.name AS home_team_name,
    ht.abbreviation AS home_team_abbr,
    g.home_score,
    -- Away team
    g.away_team_id,
    at.name AS away_team_name,
    at.abbreviation AS away_team_abbr,
    g.away_score,
    -- Game outcome
    g.period AS final_period,
    g.game_state,
    g.is_overtime,
    g.is_shootout,
    g.game_outcome,
    -- Derived fields
    CASE
        WHEN g.home_score > g.away_score THEN g.home_team_id
        WHEN g.away_score > g.home_score THEN g.away_team_id
        ELSE NULL
    END AS winner_team_id,
    CASE
        WHEN g.home_score > g.away_score THEN ht.abbreviation
        WHEN g.away_score > g.home_score THEN at.abbreviation
        ELSE NULL
    END AS winner_abbr,
    ABS(COALESCE(g.home_score, 0) - COALESCE(g.away_score, 0)) AS goal_differential,
    g.attendance,
    g.game_duration_minutes,
    g.updated_at
FROM games g
JOIN seasons s ON g.season_id = s.season_id
LEFT JOIN venues v ON g.venue_id = v.venue_id
JOIN teams ht ON g.home_team_id = ht.team_id
JOIN teams at ON g.away_team_id = at.team_id
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_game_summary_pk
    ON mv_game_summary(game_id, season_id);
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_date
    ON mv_game_summary(game_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_season
    ON mv_game_summary(season_id, game_date);
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_home_team
    ON mv_game_summary(home_team_id, game_date);
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_away_team
    ON mv_game_summary(away_team_id, game_date);
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_state
    ON mv_game_summary(game_state);
-- Partial index for final games (most queried)
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_final
    ON mv_game_summary(game_date DESC)
    WHERE game_state = 'Final';
-- Composite for team game lookup
CREATE INDEX IF NOT EXISTS idx_mv_game_summary_teams
    ON mv_game_summary(season_id, home_team_id, away_team_id);

-- ============================================================================
-- REFRESH FUNCTIONS
-- Purpose: Helper functions for refreshing materialized views
-- ============================================================================

-- Refresh all viewer views (concurrent for zero-downtime)
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
END;
$$ LANGUAGE plpgsql;

-- Refresh a single view by name
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
        ELSE
            RAISE EXCEPTION 'Unknown view: %', p_view_name;
    END CASE;

    refreshed := CURRENT_TIMESTAMP;
    RETURN refreshed;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ADDITIONAL INDEXES FOR VIEWER QUERIES
-- Purpose: Optimize common viewer query patterns on base tables
-- ============================================================================

-- Download progress: Partial indexes for viewer filters
CREATE INDEX IF NOT EXISTS idx_download_progress_failed
    ON download_progress(source_id, last_attempt_at DESC)
    WHERE status = 'failed';
CREATE INDEX IF NOT EXISTS idx_download_progress_recent
    ON download_progress(created_at DESC)
    WHERE status IN ('pending', 'failed');

-- Validation: Indexes for discrepancy viewer
CREATE INDEX IF NOT EXISTS idx_discrepancies_open
    ON discrepancies(game_id, rule_id)
    WHERE resolution_status = 'open';
CREATE INDEX IF NOT EXISTS idx_validation_results_recent_failed
    ON validation_results(run_id, created_at DESC)
    WHERE passed = FALSE;

-- Data quality: Quick access to recent scores
CREATE INDEX IF NOT EXISTS idx_dqs_recent
    ON data_quality_scores(calculated_at DESC);

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON MATERIALIZED VIEW mv_download_batch_stats IS
    'Aggregated batch progress with success/failure rates for download dashboard';
COMMENT ON MATERIALIZED VIEW mv_source_health IS
    'Per-source health status for monitoring grid';
COMMENT ON MATERIALIZED VIEW mv_player_summary IS
    'Player info with team details for data explorer';
COMMENT ON MATERIALIZED VIEW mv_game_summary IS
    'Game info with team names and venues for data explorer';
COMMENT ON FUNCTION refresh_viewer_views IS
    'Refresh all viewer materialized views (use concurrent=TRUE for zero-downtime)';
COMMENT ON FUNCTION refresh_viewer_view IS
    'Refresh a single viewer materialized view by name';

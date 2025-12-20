-- Migration: 009_validation.sql
-- Description: Validation rules, results, and data quality tracking
-- Author: Claude Code
-- Date: 2025-12-20

-- Validation rules: Configurable validation definitions
CREATE TABLE IF NOT EXISTS validation_rules (
    rule_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50) NOT NULL,  -- cross_file, internal, completeness, accuracy
    severity VARCHAR(20) DEFAULT 'warning',  -- error, warning, info
    is_active BOOLEAN DEFAULT TRUE,
    rule_sql TEXT,  -- Optional SQL for rule execution
    config JSONB,  -- Rule-specific configuration
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_validation_rules_updated_at
    BEFORE UPDATE ON validation_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default validation rules
INSERT INTO validation_rules (name, category, severity, description) VALUES
    -- Cross-file validations
    ('goal_reconciliation', 'cross_file', 'error', 'Goals match between PBP JSON, GS HTML, and ES HTML'),
    ('assist_reconciliation', 'cross_file', 'error', 'Assists match between PBP JSON and GS HTML'),
    ('player_id_consistency', 'cross_file', 'warning', 'Player IDs/names consistent across sources'),
    ('toi_validation', 'cross_file', 'warning', 'TOI matches between shift charts, TV/TH, and ES'),

    -- Internal consistency
    ('goals_vs_score', 'internal', 'error', 'Sum of period goals equals final score'),
    ('shots_vs_goals', 'internal', 'warning', 'Shots >= goals for each team'),
    ('assists_per_goal', 'internal', 'warning', 'Each goal has 0-2 assists'),
    ('period_time_bounds', 'internal', 'error', 'Events within valid period time (0-20:00)'),

    -- Completeness checks
    ('boxscore_complete', 'completeness', 'warning', 'All final games have boxscore data'),
    ('pbp_complete', 'completeness', 'warning', 'All final games have play-by-play data'),
    ('shifts_complete', 'completeness', 'warning', 'All final games have shift data'),
    ('roster_complete', 'completeness', 'info', 'All teams have current roster data'),

    -- Accuracy checks
    ('player_stats_sum', 'accuracy', 'warning', 'Player game stats sum to season totals'),
    ('team_record_accuracy', 'accuracy', 'warning', 'Team W-L-OTL matches standings')
ON CONFLICT (name) DO NOTHING;

-- Validation runs: Track each validation execution
CREATE TABLE IF NOT EXISTS validation_runs (
    run_id SERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed
    rules_checked INTEGER DEFAULT 0,
    total_passed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_warnings INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_vr_season ON validation_runs(season_id);
CREATE INDEX IF NOT EXISTS idx_vr_started ON validation_runs(started_at DESC);

-- Validation results: Individual validation outcomes
CREATE TABLE IF NOT EXISTS validation_results (
    result_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES validation_runs(run_id),
    rule_id INTEGER NOT NULL REFERENCES validation_rules(rule_id),
    game_id BIGINT,  -- NULL for non-game validations
    season_id INTEGER REFERENCES seasons(season_id),
    passed BOOLEAN NOT NULL,
    severity VARCHAR(20),
    message TEXT,
    details JSONB,  -- Structured discrepancy data
    source_values JSONB,  -- Values from each source for comparison
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_results_run ON validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_rule ON validation_results(rule_id);
CREATE INDEX IF NOT EXISTS idx_results_game ON validation_results(game_id) WHERE game_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_results_failed ON validation_results(run_id, passed) WHERE passed = FALSE;

-- Data quality scores: Aggregated quality metrics
CREATE TABLE IF NOT EXISTS data_quality_scores (
    score_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES validation_runs(run_id),
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    game_id BIGINT,  -- NULL for season-level scores

    -- Quality dimensions (0-100 scale)
    completeness_score DECIMAL(5,2),
    accuracy_score DECIMAL(5,2),
    consistency_score DECIMAL(5,2),
    timeliness_score DECIMAL(5,2),
    overall_score DECIMAL(5,2),

    -- Component counts
    total_checks INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    warning_checks INTEGER DEFAULT 0,

    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dqs_season ON data_quality_scores(season_id);
CREATE INDEX IF NOT EXISTS idx_dqs_game ON data_quality_scores(game_id) WHERE game_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dqs_overall ON data_quality_scores(overall_score);

-- Discrepancies: Detailed record of data mismatches
CREATE TABLE IF NOT EXISTS discrepancies (
    discrepancy_id SERIAL PRIMARY KEY,
    result_id INTEGER REFERENCES validation_results(result_id),
    rule_id INTEGER NOT NULL REFERENCES validation_rules(rule_id),
    game_id BIGINT,
    season_id INTEGER REFERENCES seasons(season_id),
    entity_type VARCHAR(50),  -- goal, assist, player, shift, etc.
    entity_id VARCHAR(100),  -- ID of the entity with discrepancy
    field_name VARCHAR(100),
    source_a VARCHAR(50),
    source_a_value TEXT,
    source_b VARCHAR(50),
    source_b_value TEXT,
    resolution_status VARCHAR(20) DEFAULT 'open',  -- open, resolved, ignored
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_disc_game ON discrepancies(game_id) WHERE game_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_disc_rule ON discrepancies(rule_id);
CREATE INDEX IF NOT EXISTS idx_disc_status ON discrepancies(resolution_status);
CREATE INDEX IF NOT EXISTS idx_disc_entity ON discrepancies(entity_type, entity_id);

-- Data corrections: Known fixes for data issues (e.g., Pettersson name variations)
CREATE TABLE IF NOT EXISTS data_corrections (
    correction_id SERIAL PRIMARY KEY,
    correction_type VARCHAR(50) NOT NULL,  -- name_mapping, value_override, etc.
    source VARCHAR(50),  -- Which source this applies to, NULL for all
    match_field VARCHAR(100) NOT NULL,
    match_value TEXT NOT NULL,
    corrected_value TEXT NOT NULL,
    reason TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(correction_type, source, match_field, match_value)
);

CREATE INDEX IF NOT EXISTS idx_dc_type ON data_corrections(correction_type);
CREATE INDEX IF NOT EXISTS idx_dc_match ON data_corrections(match_field, match_value);

-- Insert common name corrections (from nhl_dailyfaceoff patterns)
INSERT INTO data_corrections (correction_type, match_field, match_value, corrected_value, reason) VALUES
    ('name_mapping', 'player_name', 'Mitch Marner', 'Mitchell Marner', 'Full name standardization'),
    ('name_mapping', 'player_name', 'Matt Boldy', 'Matthew Boldy', 'Full name standardization'),
    ('name_mapping', 'player_name', 'Alex Ovechkin', 'Alexander Ovechkin', 'Full name standardization'),
    ('name_mapping', 'player_name', 'J.T. Miller', 'Jonathan Marchessault', 'Common abbreviation'),
    ('name_mapping', 'player_name', 'T.J. Oshie', 'Timothy Oshie', 'Full name standardization')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE validation_rules IS 'Configurable data validation rule definitions';
COMMENT ON TABLE validation_runs IS 'Tracks each validation batch execution';
COMMENT ON TABLE validation_results IS 'Individual validation check outcomes';
COMMENT ON TABLE data_quality_scores IS 'Aggregated quality metrics per game/season';
COMMENT ON TABLE discrepancies IS 'Detailed log of cross-source data mismatches';
COMMENT ON TABLE data_corrections IS 'Known data corrections for name/value normalization';

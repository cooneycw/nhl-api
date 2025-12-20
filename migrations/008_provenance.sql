-- Migration: 008_provenance.sql
-- Description: Data source tracking and import batch management
-- Author: Claude Code
-- Date: 2025-12-20

-- Data sources: Registry of all data sources
CREATE TABLE IF NOT EXISTS data_sources (
    source_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    source_type VARCHAR(30) NOT NULL,  -- nhl_json, html_report, shift_chart, quanthockey, dailyfaceoff
    base_url VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_ms INTEGER DEFAULT 1000,  -- Milliseconds between requests
    max_concurrent INTEGER DEFAULT 3,
    retry_count INTEGER DEFAULT 3,
    timeout_seconds INTEGER DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_data_sources_updated_at
    BEFORE UPDATE ON data_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert known data sources
INSERT INTO data_sources (name, source_type, base_url, description) VALUES
    ('nhl_schedule', 'nhl_json', 'https://api-web.nhle.com/v1/schedule', 'NHL schedule API'),
    ('nhl_boxscore', 'nhl_json', 'https://api-web.nhle.com/v1/gamecenter', 'NHL boxscore API'),
    ('nhl_pbp', 'nhl_json', 'https://api-web.nhle.com/v1/gamecenter', 'NHL play-by-play API'),
    ('nhl_roster', 'nhl_json', 'https://api-web.nhle.com/v1/roster', 'NHL roster API'),
    ('nhl_standings', 'nhl_json', 'https://api-web.nhle.com/v1/standings', 'NHL standings API'),
    ('nhl_player', 'nhl_json', 'https://api-web.nhle.com/v1/player', 'NHL player landing API'),
    ('html_gs', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Game Summary HTML report'),
    ('html_es', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Event Summary HTML report'),
    ('html_pl', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Play-by-Play HTML report'),
    ('html_fs', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Faceoff Summary HTML report'),
    ('html_fc', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Faceoff Comparison HTML report'),
    ('html_ro', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Roster Report HTML'),
    ('html_ss', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'Shot Summary HTML report'),
    ('html_tv', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'TOI Visitor HTML report'),
    ('html_th', 'html_report', 'https://www.nhl.com/scores/htmlreports', 'TOI Home HTML report'),
    ('shift_chart', 'shift_chart', 'https://api.nhle.com/stats/rest', 'NHL shift chart API'),
    ('quanthockey', 'quanthockey', 'https://www.quanthockey.com', 'QuantHockey player stats'),
    ('dailyfaceoff_lines', 'dailyfaceoff', 'https://www.dailyfaceoff.com', 'DailyFaceoff line predictions'),
    ('dailyfaceoff_roster', 'dailyfaceoff', 'https://www.dailyfaceoff.com', 'DailyFaceoff roster positions')
ON CONFLICT (name) DO NOTHING;

-- Import batches: Track each download run
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(source_id),
    season_id INTEGER REFERENCES seasons(season_id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed, cancelled
    items_total INTEGER DEFAULT 0,
    items_success INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB  -- Additional batch-specific data
);

CREATE INDEX IF NOT EXISTS idx_batches_source ON import_batches(source_id);
CREATE INDEX IF NOT EXISTS idx_batches_season ON import_batches(season_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON import_batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_started ON import_batches(started_at DESC);

-- Download progress: Track individual item downloads
CREATE TABLE IF NOT EXISTS download_progress (
    progress_id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES import_batches(batch_id),
    source_id INTEGER NOT NULL REFERENCES data_sources(source_id),
    season_id INTEGER REFERENCES seasons(season_id),
    item_key VARCHAR(100) NOT NULL,  -- e.g., game_id, player_id, date
    status VARCHAR(20) DEFAULT 'pending',  -- pending, success, failed, skipped
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    response_size_bytes INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, season_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_progress_batch ON download_progress(batch_id);
CREATE INDEX IF NOT EXISTS idx_progress_source_season ON download_progress(source_id, season_id);
CREATE INDEX IF NOT EXISTS idx_progress_status ON download_progress(status);
CREATE INDEX IF NOT EXISTS idx_progress_pending ON download_progress(source_id, season_id, status)
    WHERE status = 'pending';

-- Data provenance: Row-level source tracking (for important tables)
CREATE TABLE IF NOT EXISTS data_provenance (
    provenance_id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_key VARCHAR(100) NOT NULL,  -- Primary key of the tracked record
    source_id INTEGER NOT NULL REFERENCES data_sources(source_id),
    batch_id INTEGER REFERENCES import_batches(batch_id),
    raw_data JSONB,  -- Original source data (optional, for debugging)
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, record_key, source_id)
);

CREATE INDEX IF NOT EXISTS idx_provenance_table ON data_provenance(table_name);
CREATE INDEX IF NOT EXISTS idx_provenance_source ON data_provenance(source_id);
CREATE INDEX IF NOT EXISTS idx_provenance_batch ON data_provenance(batch_id);

COMMENT ON TABLE data_sources IS 'Registry of all data sources with rate limiting config';
COMMENT ON TABLE import_batches IS 'Tracks each download batch run with statistics';
COMMENT ON TABLE download_progress IS 'Per-item download status for checkpoint/resume';
COMMENT ON TABLE data_provenance IS 'Row-level tracking of data source origin';

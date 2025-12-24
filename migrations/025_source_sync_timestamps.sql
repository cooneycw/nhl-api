-- Migration: 025_source_sync_timestamps.sql
-- Description: Track last successful sync per source/season/game-type for delta downloads
-- Author: Claude Code
-- Date: 2025-12-24
-- Issue: #248

-- Source sync timestamps: Track delta sync state for smart downloads
-- This enables the simplified download UI to only fetch games completed since last sync
CREATE TABLE IF NOT EXISTS source_sync_timestamps (
    sync_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(source_id),
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    game_type INTEGER NOT NULL,  -- 1=preseason, 2=regular, 3=playoffs, 0=external (no game type)
    last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    items_synced_count INTEGER DEFAULT 0,
    last_batch_id INTEGER REFERENCES import_batches(batch_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one sync record per source/season/game_type combination
    UNIQUE(source_id, season_id, game_type)
);

-- Index for fast lookups by source and season
CREATE INDEX IF NOT EXISTS idx_sync_timestamps_source_season
    ON source_sync_timestamps(source_id, season_id);

-- Index for finding stale syncs
CREATE INDEX IF NOT EXISTS idx_sync_timestamps_last_synced
    ON source_sync_timestamps(last_synced_at DESC);

-- Trigger for updated_at
CREATE TRIGGER update_source_sync_timestamps_updated_at
    BEFORE UPDATE ON source_sync_timestamps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE source_sync_timestamps IS 'Tracks last successful sync per source/season/game-type for delta downloads';
COMMENT ON COLUMN source_sync_timestamps.game_type IS '1=preseason, 2=regular, 3=playoffs, 0=external sources (no game type filtering)';
COMMENT ON COLUMN source_sync_timestamps.last_synced_at IS 'Timestamp of last successful sync completion';
COMMENT ON COLUMN source_sync_timestamps.items_synced_count IS 'Number of items synced in the last batch';
COMMENT ON COLUMN source_sync_timestamps.last_batch_id IS 'Reference to the import_batches entry for the last sync';

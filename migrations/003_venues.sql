-- Migration: 003_venues.sql
-- Description: Venue/arena information table
-- Author: Claude Code
-- Date: 2025-12-20

-- Venues table: Arena information for games
CREATE TABLE IF NOT EXISTS venues (
    venue_id SERIAL PRIMARY KEY,
    nhl_venue_id INTEGER UNIQUE,  -- NHL API venue ID if available
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50),
    state_province VARCHAR(50),
    country VARCHAR(50) DEFAULT 'USA',
    capacity INTEGER,
    timezone VARCHAR(50),
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_venues_nhl_id ON venues(nhl_venue_id) WHERE nhl_venue_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city);

CREATE TRIGGER update_venues_updated_at
    BEFORE UPDATE ON venues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE venues IS 'NHL arena/venue information with location data';
COMMENT ON COLUMN venues.nhl_venue_id IS 'Official NHL API venue identifier';

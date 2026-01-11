# Implementation Plan: Second-by-Second Analytics

## Summary

Build a second-level granular analytics pipeline that combines shift data and
play-by-play events to create the foundational dataset for Bayesian/GNN analysis.

## Constitution Check

- [x] P1 Second-by-Second First - This IS the target feature
- [x] P2 Validation Parity - Will validate against official stats
- [x] P3 Data Consolidation - Uses existing shift/PBP data
- [x] P4 oneNinety-Ready - API-first design, no UI coupling
- [x] P5 Spec Before Code - This spec exists

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Shift Charts   │    │  Play-by-Play   │
│  (DB table)     │    │  (DB table)     │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────┐
│       Second-Level Expansion            │
│  (shift start/end → second resolution)  │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│       Event Attribution Join            │
│  (match events to on-ice players)       │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│       SecondSnapshot Table              │
│  (game_id, period, second, players,     │
│   events, situation_code)               │
└────────────────────┬────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  Matchup Table  │    │  Export (Parquet)│
│  (player vs     │    │  for ML/GNN      │
│   player pairs) │    │                  │
└─────────────────┘    └─────────────────┘
```

## Data Model

### SecondSnapshot (new table)
```sql
CREATE TABLE second_snapshots (
    id BIGSERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    period INTEGER NOT NULL,
    elapsed_seconds INTEGER NOT NULL,  -- 0-1200 per period

    -- Home team on ice (up to 6 skaters + 1 goalie)
    home_skater_1 INTEGER,
    home_skater_2 INTEGER,
    home_skater_3 INTEGER,
    home_skater_4 INTEGER,
    home_skater_5 INTEGER,
    home_skater_6 INTEGER,
    home_goalie INTEGER,

    -- Away team on ice
    away_skater_1 INTEGER,
    away_skater_2 INTEGER,
    away_skater_3 INTEGER,
    away_skater_4 INTEGER,
    away_skater_5 INTEGER,
    away_skater_6 INTEGER,
    away_goalie INTEGER,

    -- Situation
    situation_code VARCHAR(10),  -- "5v5", "5v4", "4v4", "EN5v6", etc.
    home_strength INTEGER,
    away_strength INTEGER,

    -- Events this second (JSONB for flexibility)
    events JSONB DEFAULT '[]',

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(game_id, period, elapsed_seconds)
);

CREATE INDEX idx_second_snapshots_game ON second_snapshots(game_id);
CREATE INDEX idx_second_snapshots_situation ON second_snapshots(situation_code);
```

### PlayerMatchup (derived/materialized)
```sql
CREATE MATERIALIZED VIEW player_matchups AS
SELECT
    game_id,
    home_player_id,
    away_player_id,
    situation_code,
    COUNT(*) as seconds_together,
    SUM(CASE WHEN events @> '[{"team": "home"}]' THEN 1 ELSE 0 END) as home_events,
    SUM(CASE WHEN events @> '[{"team": "away"}]' THEN 1 ELSE 0 END) as away_events
FROM second_snapshots
CROSS JOIN LATERAL (
    SELECT unnest(ARRAY[home_skater_1, home_skater_2, ...]) as home_player_id
) h
CROSS JOIN LATERAL (
    SELECT unnest(ARRAY[away_skater_1, away_skater_2, ...]) as away_player_id
) a
WHERE home_player_id IS NOT NULL AND away_player_id IS NOT NULL
GROUP BY game_id, home_player_id, away_player_id, situation_code;
```

## Implementation Phases

### Phase 1: Core Pipeline (Wave 1)
1. Create database schema
2. Build shift expansion service (MM:SS → second resolution)
3. Build event attribution service
4. Create SecondSnapshot table population

### Phase 2: Validation (Wave 2)
1. Validate player counts match shift totals
2. Validate events attributed correctly
3. Cross-check with boxscore totals

### Phase 3: Analytics Support (Wave 3)
1. Create matchup materialized view
2. Build Parquet export for ML
3. Add aggregation functions

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data volume too large | Medium | High | Use partitioning by season |
| Shift timing precision | Medium | Medium | Validate sample games manually |
| Event time misalignment | Low | High | Use fuzzy matching within 2 seconds |
| Performance on queries | Medium | Medium | Proper indexing, materialized views |

## Dependencies

- #247 must be resolved for validation framework
- #257 gamecenter landing may provide additional context
- Existing shift_charts and play_by_play tables must be populated

## Testing Strategy

1. **Unit Tests**: Shift expansion logic, situation calculation
2. **Integration Tests**: Full pipeline for sample games
3. **Validation Tests**: Compare totals to official stats
4. **Performance Tests**: Query time for season-level analysis

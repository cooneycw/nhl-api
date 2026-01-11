# Feature Specification: Second-by-Second Analytics

## Overview

Build a granular analytics dataset that captures every second of NHL game play with
complete player combination and event data. This is the foundational dataset for
Bayesian estimation and graph neural network analysis.

## User Stories

### US1: Second-Level On-Ice Tracking [P0]
**As a** data analyst,
**I want** to know which players were on the ice for each second of play,
**So that** I can attribute events to specific player combinations.

**Acceptance Criteria:**
- [ ] For every second of game time, identify all 12 skaters (6 per team)
- [ ] Track goalies on ice for each second
- [ ] Handle edge cases: delayed penalties, empty net, overtime
- [ ] Data validated against official shift charts

### US2: Cross-Team Matchup Analysis [P0]
**As a** data analyst,
**I want** to see which opposing players were on the ice together,
**So that** I can analyze matchup effectiveness.

**Acceptance Criteria:**
- [ ] For each second, track home vs. away player matchups
- [ ] Calculate total ice time for each player-vs-player matchup
- [ ] Support rollup by line combinations vs. opposing lines
- [ ] Identify defensive zone matchups separately from offensive zone

### US3: Event Attribution [P0]
**As a** data analyst,
**I want** events (goals, shots, hits) attributed to on-ice players,
**So that** I can build graph models of player interactions.

**Acceptance Criteria:**
- [ ] Each event includes all on-ice players (both teams)
- [ ] Primary/secondary player attribution preserved
- [ ] Event coordinates (x, y) included for spatial analysis
- [ ] Situation code (5v5, 5v4, etc.) calculated from player counts

### US4: Flexible Aggregation [P1]
**As a** data analyst,
**I want** to roll up second-level data to any granularity,
**So that** I can analyze at shift, period, game, or season level.

**Acceptance Criteria:**
- [ ] Aggregation to shift-level preserves all metrics
- [ ] Period-level summaries available
- [ ] Game-level totals match official stats
- [ ] Season-level rollups for player combinations

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Delayed penalty | Track situation accurately during delay |
| Empty net | Goalie field NULL, situation reflects 6v5 |
| Overtime (3v3) | Correctly track reduced player counts |
| Penalty shot | Track 1v1 + goalie situation |
| Coach's challenge | Handle time reversals |
| TV timeout | Mark as stoppage, no on-ice attribution |

## Out of Scope

- Real-time streaming (batch processing only for now)
- Video synchronization
- Advanced metrics calculation (Corsi, Fenwick - separate feature)
- Visualization/dashboards (covered by viewer)

## Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Expand shifts to second-level resolution | Must | US1 |
| R2 | Track all 12 skaters per second | Must | US1 |
| R3 | Track goalies per second | Must | US1 |
| R4 | Calculate situation codes from player counts | Must | US3 |
| R5 | Join play-by-play events to on-ice data | Must | US3 |
| R6 | Store matchup pairs (home player vs away player) | Must | US2 |
| R7 | Include event coordinates | Must | US3 |
| R8 | Support period/game aggregation | Should | US4 |
| R9 | Export to Parquet/Arrow for ML pipelines | Should | US4 |
| R10 | Validate totals against official stats | Should | US1 |

## Success Criteria

- [ ] All acceptance criteria in US1-US4 met
- [ ] Data for 2024-2025 season processed without errors
- [ ] Shift totals match official NHL stats within 5 seconds per game
- [ ] Event attribution validated against boxscore totals
- [ ] Export format compatible with PyTorch Geometric / NetworkX

## Technical Notes

**Data Sources Required:**
- Shift charts (NHL Stats API) - currently implemented
- Play-by-play (NHL JSON API) - currently implemented
- Boxscore (NHL JSON API) - for validation

**Storage Considerations:**
- ~3600 seconds per game × ~20 players = 72,000 rows per game
- ~1300 games per season = ~94M rows per season
- Consider partitioning by season/game
- May need columnar storage (Parquet) for analytics queries

**Related Issues:**
- Depends on #247 (validation parity) for data quality
- Depends on #257 (missing sources) for gamecenter landing data

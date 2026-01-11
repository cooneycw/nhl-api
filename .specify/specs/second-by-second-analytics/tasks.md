# Tasks: Second-by-Second Analytics

## Task Format
[ID] [Priority] [Story] Description `path/to/file.py` (depends on X)

## Wave 1: Core Pipeline

### Database Schema
- [ ] **T001** [P0] [US1] Create second_snapshots table migration `src/nhl_api/models/second_snapshots.py`
- [ ] **T002** [P0] [US1] Add SQLAlchemy model for SecondSnapshot `src/nhl_api/models/second_snapshots.py`
- [ ] **T003** [P0] [US1] Create indexes for game_id, situation_code `src/nhl_api/models/second_snapshots.py`

### Shift Expansion Service
- [ ] **T004** [P0] [US1] Create ShiftExpander class `src/nhl_api/services/analytics/shift_expander.py`
- [ ] **T005** [P0] [US1] Parse shift start/end times to seconds `src/nhl_api/services/analytics/shift_expander.py` (depends on T004)
- [ ] **T006** [P0] [US1] Generate second-by-second records from shifts `src/nhl_api/services/analytics/shift_expander.py` (depends on T005)
- [ ] **T007** [P0] [US1] Handle edge cases: OT, delayed penalty `src/nhl_api/services/analytics/shift_expander.py` (depends on T006)

### Event Attribution
- [ ] **T008** [P0] [US3] Create EventAttributor class `src/nhl_api/services/analytics/event_attributor.py`
- [ ] **T009** [P0] [US3] Join PBP events to second snapshots `src/nhl_api/services/analytics/event_attributor.py` (depends on T008)
- [ ] **T010** [P0] [US3] Handle time fuzzy matching (±2 sec) `src/nhl_api/services/analytics/event_attributor.py` (depends on T009)

### Situation Calculator
- [ ] **T011** [P0] [US3] Create SituationCalculator class `src/nhl_api/services/analytics/situation.py`
- [ ] **T012** [P0] [US3] Calculate situation code from player counts `src/nhl_api/services/analytics/situation.py` (depends on T011)
- [ ] **T013** [P0] [US3] Handle empty net detection `src/nhl_api/services/analytics/situation.py` (depends on T012)

**Checkpoint Wave 1:** Can generate second_snapshots table for a single game

---

## Wave 2: Validation & Quality

### Validation Suite
- [ ] **T014** [P1] [US1] Validate player shift totals match `tests/integration/analytics/test_shift_totals.py`
- [ ] **T015** [P1] [US3] Validate event counts match boxscore `tests/integration/analytics/test_event_counts.py`
- [ ] **T016** [P1] [US1] Validate situation codes correct `tests/integration/analytics/test_situation_codes.py`

### Cross-Source Validation
- [ ] **T017** [P1] [US1] Compare to HTML shift reports `src/nhl_api/validation/analytics_validation.py`
- [ ] **T018** [P1] [US3] Compare event attribution to official scorer `src/nhl_api/validation/analytics_validation.py` (depends on T017)

**Checkpoint Wave 2:** Second-by-second data validated against official sources

---

## Wave 3: Matchup Analysis

### Matchup Calculation
- [ ] **T019** [P0] [US2] Create player_matchups materialized view `src/nhl_api/models/matchups.py`
- [ ] **T020** [P0] [US2] Build matchup aggregation queries `src/nhl_api/services/analytics/matchup_service.py`
- [ ] **T021** [P0] [US2] Calculate ice time by player pair `src/nhl_api/services/analytics/matchup_service.py` (depends on T020)

### Zone Analysis
- [ ] **T022** [P1] [US2] Add zone detection from event coords `src/nhl_api/services/analytics/zone_detection.py`
- [ ] **T023** [P1] [US2] Track defensive zone matchups separately `src/nhl_api/services/analytics/zone_detection.py` (depends on T022)

**Checkpoint Wave 3:** Can query matchup ice time for any player pair

---

## Wave 4: Export & Integration

### Parquet Export
- [ ] **T024** [P1] [US4] Create Parquet export service `src/nhl_api/services/analytics/export.py`
- [ ] **T025** [P1] [US4] Schema for PyTorch Geometric compatibility `src/nhl_api/services/analytics/export.py` (depends on T024)
- [ ] **T026** [P1] [US4] Export season-level matchup data `src/nhl_api/services/analytics/export.py` (depends on T025)

### CLI Commands
- [ ] **T027** [P1] [US4] Add `analytics build` CLI command `src/nhl_api/cli/analytics.py`
- [ ] **T028** [P1] [US4] Add `analytics export` CLI command `src/nhl_api/cli/analytics.py` (depends on T027)
- [ ] **T029** [P1] [US4] Add `analytics validate` CLI command `src/nhl_api/cli/analytics.py` (depends on T027)

**Checkpoint Wave 4:** Can build and export full season analytics data

---

## Wave 5: Aggregation Functions

### Rollup Services
- [ ] **T030** [P2] [US4] Shift-level aggregation `src/nhl_api/services/analytics/aggregation.py`
- [ ] **T031** [P2] [US4] Period-level aggregation `src/nhl_api/services/analytics/aggregation.py` (depends on T030)
- [ ] **T032** [P2] [US4] Game-level aggregation `src/nhl_api/services/analytics/aggregation.py` (depends on T031)
- [ ] **T033** [P2] [US4] Season-level line combination stats `src/nhl_api/services/analytics/aggregation.py` (depends on T032)

**Checkpoint Wave 5:** Flexible aggregation at any level

---

## Issue Sync

| Wave | Tasks | GitHub Issue | Status |
|------|-------|--------------|--------|
| Wave 1: Core Pipeline | T001-T013 | #259 | synced |
| Wave 2: Validation | T014-T018 | #260 | synced |
| Wave 3: Matchups | T019-T023 | #261 | synced |
| Wave 4: Export | T024-T029 | #262 | synced |
| Wave 5: Aggregation | T030-T033 | #263 | synced |

---

## Dependencies

- **Blocking**: Issues #247, #257 should be addressed first for data quality
- **Data Required**: Shift charts and play-by-play data must be downloaded for target season
- **Infrastructure**: PostgreSQL with sufficient storage for ~100M rows

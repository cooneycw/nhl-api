# NHL-API Constitution

## Core Purpose

Build a second-by-second player combination analytics platform that enables
Bayesian estimation and graph neural network analysis of NHL game data.
Future integration with oneNinety Django dashboard.

## The Target Feature

Every game produces a dataset where each second of play shows:
- Which players are on ice (both teams)
- What events occurred (shots, goals, hits, etc.)
- Game situation (5v5, PP, PK, etc.)
- Matchup combinations (who vs. who)

This granular view enables any rollup while preserving the full signal.

**Data Model:**
```
| Second | Home Ice (6) | Away Ice (6) | Event | Situation |
|--------|--------------|--------------|-------|-----------|
| 0:01   | [player_ids] | [player_ids] | Faceoff | 5v5 |
| 0:02   | [player_ids] | [player_ids] | Shot | 5v5 |
```

**End Goals:**
- Bayesian parameter estimation for player effectiveness
- Graph neural network modeling of player interactions
- Flexible aggregation from second-level granularity

## Principles

### P1: Second-by-Second First (TARGET)

All work prioritizes building the core analytics view:
1. Combine shift data + play-by-play at second-level granularity
2. Cross-team player combination tracking
3. Event attribution to on-ice players

**No new UI features until this core is built.**

### P2: Validation Parity

Match or exceed nhl_apishift_v2's data quality assurance:
- All sources trigger validation (currently 16% → target 100%)
- Reconciliation pipeline runs automatically
- Quality metrics tracked and reported
- Reference: Issue #247

### P3: Data Consolidation Complete

Complete legacy repo consolidation to support analytics:
- All required endpoints from Issue #257
- All validation from Issue #247
- MDC query integration for advanced stats

**Legacy repos to consolidate:**
- cooneycw/NHL, nhl_apishift_v2, nhl_apishift
- cooneycw/nhl_apimdc (MDC queries)
- cooneycw/nhl_dailyfaceoff (web scraping)
- cooneycw/nhl_statsroutine, nhl_quantdata
- cooneycw/NHLapiV3, NHLstats

### P4: oneNinety-Ready Architecture

Build for eventual Django integration:
- Modular, reusable components
- API-first design (FastAPI → Django REST possible)
- No React-specific coupling in data layer
- Current viewer is proof-of-concept, not production

### P5: Spec Before Code

All features >4 hours require spec approval.
Use `/spec:create` before implementation.

## Priority Order

1. **P0**: Second-by-second analytics (the target)
2. **P1**: Validation parity (#247)
3. **P1**: Missing data sources (#257)
4. **P2**: Reconciliation pipeline
5. **P3**: UI polish (frozen until P0-P2 complete)

## Known Deviations

Document any exceptions to these principles here with rationale.

| Date | Deviation | Rationale | Approved By |
|------|-----------|-----------|-------------|
| - | - | - | - |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-24 | Initial constitution with target feature |

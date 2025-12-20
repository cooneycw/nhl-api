# Test Data Fixtures

This directory contains JSON fixtures representing sample NHL API responses.
These files are used by the `load_json_fixture` fixture in `conftest.py`.

## Available Fixtures

| File | Description |
|------|-------------|
| `player_response.json` | Sample player data (Connor McDavid) |
| `player_stats_response.json` | Player statistics for a season |
| `team_response.json` | Sample team data (Edmonton Oilers) |
| `game_response.json` | Completed game with linescore |
| `schedule_response.json` | Daily schedule with multiple games |
| `standings_response.json` | Division standings with team records |

## Usage

```python
def test_parse_player(load_json_fixture):
    """Test parsing a player response."""
    data = load_json_fixture("player_response.json")
    assert data["fullName"] == "Connor McDavid"
```

## Adding New Fixtures

1. Create a JSON file with realistic NHL API response structure
2. Use actual field names from the NHL API
3. Include reasonable sample data
4. Add the file to this README

## Data Sources

Fixtures are based on the NHL Stats API structure. For the latest API
documentation, refer to the unofficial NHL API docs.

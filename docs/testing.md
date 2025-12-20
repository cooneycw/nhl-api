# Testing Guide

This document describes the testing infrastructure for the NHL API project.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures (auto-loaded by pytest)
├── data/                # JSON test fixtures
│   ├── player_response.json
│   ├── player_stats_response.json
│   ├── team_response.json
│   ├── game_response.json
│   ├── schedule_response.json
│   ├── standings_response.json
│   └── README.md
├── unit/                # Fast unit tests
│   ├── test_sample.py
│   └── test_fixtures.py
├── integration/         # Integration tests (external dependencies)
└── data_validation/     # Data integrity tests
```

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v

# Run without coverage (faster)
pytest --no-cov

# Run specific test file
pytest tests/unit/test_fixtures.py
```

## Available Fixtures

All fixtures are defined in `tests/conftest.py` and automatically available
in any test file.

### Sample Data Fixtures

| Fixture | Description |
|---------|-------------|
| `sample_player_data` | Connor McDavid player data |
| `sample_player_stats` | Player season statistics |
| `sample_goalie_data` | Stuart Skinner goalie data |
| `sample_team_data` | Edmonton Oilers team data |
| `sample_team_roster` | Partial team roster |
| `sample_game_data` | Completed game with scores |
| `sample_schedule_data` | Daily schedule |

**Example:**

```python
@pytest.mark.unit
def test_player_name(sample_player_data):
    assert sample_player_data["fullName"] == "Connor McDavid"
```

### JSON Fixture Loader

| Fixture | Description |
|---------|-------------|
| `test_data_dir` | Path to `tests/data/` directory |
| `load_json_fixture` | Factory to load JSON files from `tests/data/` |

**Example:**

```python
@pytest.mark.unit
def test_parse_response(load_json_fixture):
    data = load_json_fixture("player_response.json")
    assert data["id"] == 8478402
```

### Mock API Client

| Fixture | Description |
|---------|-------------|
| `mock_http_response` | Mock HTTP response object |
| `mock_api_client` | Sync mock with pre-configured sample data |
| `mock_async_api_client` | Async mock for async code |

**Example:**

```python
@pytest.mark.unit
def test_fetch_player(mock_api_client):
    player = mock_api_client.get_player(8478402)
    assert player["fullName"] == "Connor McDavid"
    mock_api_client.get_player.assert_called_once_with(8478402)

@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_fetch(mock_async_api_client):
    player = await mock_async_api_client.get_player(8478402)
    assert player["fullName"] == "Connor McDavid"
```

### Temporary Storage

| Fixture | Description |
|---------|-------------|
| `temp_data_dir` | Temp directory with cache/, raw/, processed/ subdirs |
| `temp_cache_file` | Pre-populated cache file |
| `temp_db_path` | Path for temporary SQLite database |

**Example:**

```python
@pytest.mark.unit
def test_cache_write(temp_data_dir):
    cache_file = temp_data_dir / "cache" / "players.json"
    cache_file.write_text('{"players": []}')
    assert cache_file.exists()
```

### Environment Variables

| Fixture | Description |
|---------|-------------|
| `mock_env_vars` | Sets NHL_API_* environment variables |

**Example:**

```python
@pytest.mark.unit
def test_config(mock_env_vars):
    import os
    assert os.environ["NHL_API_BASE_URL"] == "https://api-web.nhle.com"
```

### Utility Fixtures

| Fixture | Description |
|---------|-------------|
| `freeze_time` | Factory to freeze datetime for tests |

**Example:**

```python
@pytest.mark.unit
def test_cache_expiry(freeze_time):
    freeze_time("2024-12-20T12:00:00")
    # datetime.now() now returns the frozen time
```

## Test Markers

Tests are marked with the following pytest markers:

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Fast unit tests, no external dependencies |
| `@pytest.mark.integration` | Tests requiring external services |
| `@pytest.mark.data_validation` | Data integrity tests |
| `@pytest.mark.asyncio` | Async tests (auto-detected) |

## Coverage Requirements

- Minimum coverage: 80%
- Coverage is enforced by pytest-cov
- Coverage report shows missing lines

```bash
# View coverage report
pytest --cov-report=html
open htmlcov/index.html
```

## Adding New Fixtures

1. Add fixture to `tests/conftest.py`
2. Add docstring with usage example
3. Add test in `tests/unit/test_fixtures.py`
4. Update this documentation

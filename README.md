# NHL API

A consolidated NHL data API project for downloading, storing, and exploring NHL statistics.

## Project Architecture

```
src/nhl_api/
├── downloaders/          # Data acquisition layer
│   ├── base/             # Abstract base classes & utilities
│   │   ├── base_downloader.py   # Core downloader with retry, rate limiting
│   │   ├── rate_limiter.py      # Token bucket rate limiter
│   │   └── retry_handler.py     # Exponential backoff retry logic
│   ├── progress/         # Download progress tracking
│   └── sources/          # Source-specific implementations
│       └── nhl_json/     # NHL JSON API downloaders
│           ├── schedule.py      # Season schedules
│           ├── boxscore.py      # Game boxscores
│           ├── play_by_play.py  # Play-by-play data
│           └── roster.py        # Team rosters
├── viewer/               # Data exploration layer (FastAPI)
│   ├── main.py           # Application entry point
│   ├── routers/          # API endpoints
│   │   ├── entities.py   # Players, teams, games
│   │   ├── monitoring.py # Download progress dashboard
│   │   └── health.py     # Health checks
│   └── schemas/          # Pydantic models
├── services/             # Shared services
│   └── db/               # PostgreSQL connection & repos
├── config/               # Configuration & secrets
└── utils/                # HTTP client, helpers
```

### Downloader Architecture

All downloaders extend `BaseDownloader` which provides:
- **Rate limiting** - Token bucket algorithm to respect API limits
- **Retry logic** - Exponential backoff with jitter for transient failures
- **Progress tracking** - Callbacks for UI/logging integration
- **Async context manager** - Clean resource management

```python
async with BoxscoreDownloader(config) as downloader:
    async for result in downloader.download_season(20242025):
        print(f"Downloaded game {result.game_id}")
```

### Data Viewer

FastAPI backend with React frontend for exploring downloaded data:
- Swagger UI at `http://localhost:8000/docs`
- Player/Team/Game entity endpoints
- Download monitoring dashboard

## Setup

```bash
# Clone and setup environment
git clone git@github.com:cooneycw/nhl-api.git
cd nhl-api
conda env create -f environment.yml
conda activate nhl-api

# Configure database credentials
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## Running the Data Viewer

```bash
# Start backend only
./scripts/start-viewer.sh

# Start with React frontend
./scripts/start-viewer.sh --full

# Stop
./scripts/start-viewer.sh --stop
```

## Development Workflow

This project uses git worktrees for parallel issue development. See `CLAUDE.md` for details.

## Acknowledgments

This project would not be possible without:

- **[Zmalski/NHL-API-Reference](https://github.com/Zmalski/NHL-API-Reference)** - Comprehensive unofficial documentation of NHL API endpoints. An invaluable resource for understanding the API's data structures and available endpoints.

## Legal Disclaimer

This is an **unofficial project** and is not affiliated with, endorsed by, or connected to the National Hockey League (NHL), NHL Enterprises, L.P., or any of its subsidiaries or affiliates.

- NHL and the NHL Shield are registered trademarks of the National Hockey League
- All NHL logos, team names, and marks are property of the NHL and its teams
- Data accessed through the NHL API is subject to the NHL's terms of service
- This project is intended for personal, non-commercial use only

The author makes no guarantees about the accuracy or availability of the data. Use at your own risk.

## License

Private repository - all rights reserved.

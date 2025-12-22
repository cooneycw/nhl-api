# NHL Data Viewer - User Guide

The NHL Data Viewer provides a web interface for exploring downloaded NHL data, monitoring data pipelines, and validating data integrity.

## Quick Start

```bash
# Start the viewer (backend + frontend)
./scripts/start-viewer.sh --full

# Open in browser
open http://localhost:5173
```

## Pages Overview

### Dashboard (`/`)

The main landing page showing:

- **Health Cards** - Database connectivity and service status
- **Stats Summary** - Active batches, items processed today, success rate
- **Source Health Grid** - Status of each data source (schedule, boxscore, play-by-play, etc.)
- **Active Batches** - Currently running download batches with progress
- **Progress Chart** - 24-hour download activity timeline
- **Recent Failures** - Failed downloads with retry buttons

### Coverage (`/coverage`)

Data completeness dashboard with "gas tank" gauges showing:

- Games Downloaded vs Scheduled
- Boxscore Data completion
- Play-by-Play coverage
- Shift Charts coverage
- Player Profiles
- HTML Reports

Select different seasons to see coverage across years.

### Downloads (`/downloads`)

Trigger new data downloads:

1. **Select Seasons** - Check one or more seasons to download
2. **Select Sources** - Choose data types (Schedule, Boxscore, Play-by-Play, etc.)
3. **Start Download** - Click to begin async download
4. **Monitor Progress** - Progress bars update automatically

Active downloads can be cancelled from this page.

### Players (`/players`)

Browse all NHL players with:

- **Search** - Find players by name
- **Position Filter** - Filter by C, LW, RW, D, or G
- **Team Filter** - Filter by current team
- **Pagination** - Navigate through results

Click any player to view their detail page.

### Player Detail (`/players/:id`)

Individual player information:

- Biographical data (age, height, weight, nationality)
- Current team and roster status
- Captain/Alternate designations
- Game log with per-game stats

### Teams (`/teams`)

All NHL teams organized by:

- Conference (Eastern/Western)
- Division (Atlantic, Metropolitan, Central, Pacific)

Click any team to view roster and games.

### Team Detail (`/teams/:id`)

Team information including:

- Venue details
- Current roster (sorted by position)
- Recent game results

### Games (`/games`)

Browse all games with filters:

- **Season** - Filter by season (e.g., 2024-2025)
- **Team** - Filter by team participation
- **Date Range** - Start and end dates
- **Game Type** - Preseason, Regular, Playoffs, All-Star
- **Pagination** - Navigate results

### Game Detail (`/games/:id`)

Comprehensive game view with tabs:

- **Summary** - Final score, venue, date/time
- **Events** - Play-by-play timeline
- **Stats** - Player statistics for both teams
- **Shifts** - Time-on-ice breakdown by player

### Validation (`/validation`)

Data integrity checks:

- Compare data across sources (JSON API vs HTML reports)
- Identify missing or inconsistent records
- Drill down to per-game reconciliation

### Game Reconciliation (`/validation/game/:id`)

Per-game data validation showing:

- Discrepancies between sources
- Field-by-field comparisons
- Status indicators (match, mismatch, missing)

## Features

### Dark Mode

Toggle dark mode via the sun/moon icon in the header. Supports:

- Light mode
- Dark mode
- System preference (auto)

Preference is saved to localStorage.

### Navigation

The sidebar provides quick access to all pages:

- Dashboard (home icon)
- Downloads
- Coverage
- Players
- Teams
- Games
- Validation

External links to API documentation:

- Swagger UI (`/docs`)
- ReDoc (`/redoc`)

### Loading States

All pages show skeleton loading states while fetching data, providing visual feedback during API calls.

### Error Handling

When API calls fail, pages display error messages with:

- Error description
- Retry button (where applicable)

## API Documentation

Interactive API documentation is available at:

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI - try endpoints interactively |
| http://localhost:8000/redoc | ReDoc - comprehensive reference docs |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search (on Player/Game pages) |
| `Escape` | Close modals/dialogs |

## Troubleshooting

### "Unable to locate credentials"

The viewer requires database credentials. Ensure `.env` file exists:

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### Empty Data

Data must be downloaded before it can be viewed:

1. Go to Downloads page (`/downloads`)
2. Select seasons and sources
3. Click "Start Download"
4. Monitor progress on Dashboard

### Connection Errors

If health cards show "Offline":

1. Check database is running
2. Verify credentials in `.env`
3. Check backend logs: `tail -f /tmp/nhl-viewer-backend.log`

### Frontend Not Loading

If only backend is running:

```bash
# Stop and restart with frontend
./scripts/start-viewer.sh --stop
./scripts/start-viewer.sh --full
```

## Development

### Start in Dev Mode

```bash
# Backend only (for API development)
./scripts/start-viewer.sh

# Full stack
./scripts/start-viewer.sh --full
```

### View Logs

```bash
# Backend
tail -f /tmp/nhl-viewer-backend.log

# Frontend
tail -f /tmp/nhl-viewer-frontend.log
```

### Check Status

```bash
./scripts/start-viewer.sh --status
```

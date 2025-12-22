# HTML Report Storage

This directory contains raw NHL HTML game reports downloaded for cross-source validation.

## Directory Structure

```
data/html/
├── {season}/           # Season ID (e.g., 20242025)
│   ├── {report_type}/  # Report type code
│   │   └── {game_id}.HTM
```

### Example

```
data/html/
├── 20242025/
│   ├── ES/             # Event Summary reports
│   │   ├── 2024020001.HTM
│   │   ├── 2024020002.HTM
│   │   └── ...
│   ├── GS/             # Game Summary reports
│   │   ├── 2024020001.HTM
│   │   └── ...
│   ├── PL/             # Play-by-Play reports
│   ├── FS/             # Faceoff Summary reports
│   ├── FC/             # Faceoff Comparison reports
│   ├── RO/             # Roster reports
│   ├── SS/             # Shot Summary reports
│   ├── TH/             # Time on Ice (Home) reports
│   └── TV/             # Time on Ice (Visitor) reports
└── 20232024/
    └── ...
```

## Report Types

| Code | Report Name | Description |
|------|-------------|-------------|
| ES | Event Summary | Player statistics summary |
| GS | Game Summary | Game overview and scoring |
| PL | Play-by-Play | Detailed play-by-play events |
| FS | Faceoff Summary | Faceoff statistics by zone |
| FC | Faceoff Comparison | Head-to-head faceoff matchups |
| RO | Roster | Team rosters and officials |
| SS | Shot Summary | Shot locations and types |
| TH | Time on Ice (Home) | Shift-by-shift for home team |
| TV | Time on Ice (Visitor) | Shift-by-shift for away team |

## Game ID Format

Game IDs are 10-digit numbers formatted as `YYYYTTNNNN`:
- `YYYY` = Season start year (e.g., 2024)
- `TT` = Game type:
  - `01` = Preseason
  - `02` = Regular season
  - `03` = Playoffs
  - `04` = All-Star
- `NNNN` = Game number (e.g., 0001, 0500)

### Examples
- `2024020001` = 2024-25 regular season game #1
- `2024030001` = 2024-25 playoff game #1
- `2023020500` = 2023-24 regular season game #500

## Usage

### Automatic Storage

HTML reports are automatically saved when downloaded using any HTML downloader:

```python
from nhl_api.downloaders.sources.html import GameSummaryDownloader

async with GameSummaryDownloader() as downloader:
    # Downloads and automatically persists HTML to disk
    result = await downloader.download_game(2024020500)
```

### Manual Storage

You can also use the HTMLStorageManager directly:

```python
from nhl_api.utils import HTMLStorageManager

manager = HTMLStorageManager()

# Save HTML
manager.save_html(
    season="20242025",
    report_type="ES",
    game_id=2024020001,
    html="<html>...</html>"
)

# Load HTML
html = manager.load_html(
    season="20242025",
    report_type="ES",
    game_id=2024020001
)

# Check if exists
exists = manager.exists("20242025", "ES", 2024020001)

# List all reports
reports = manager.list_reports(season="20242025", report_type="ES")
```

### Disable Persistence

HTML persistence can be disabled via configuration:

```python
from nhl_api.downloaders.sources.html import (
    GameSummaryDownloader,
    HTMLDownloaderConfig,
)

config = HTMLDownloaderConfig(persist_html=False)

async with GameSummaryDownloader(config) as downloader:
    # Downloads but does NOT persist to disk
    result = await downloader.download_game(2024020500)
```

## Purpose

HTML reports serve as the authoritative source of truth for NHL data validation:

1. **Cross-Source Validation**: Compare JSON API data against official HTML reports
2. **Data Reconciliation**: Identify discrepancies between different data sources
3. **Historical Analysis**: Preserve raw data for future re-processing
4. **Regression Testing**: Use cached HTML to test parser changes without re-downloading

## Storage Management

### Disk Usage

Each HTML report is approximately 50KB - 2MB depending on report type:
- Event Summary (ES): ~100-200KB
- Play-by-Play (PL): ~500KB-2MB
- Roster (RO): ~50-100KB

For a full season (~1300 games × 9 reports):
- Estimated total: 10-25GB per season

### Cleanup

To remove old HTML reports:

```python
from nhl_api.utils import HTMLStorageManager

manager = HTMLStorageManager()

# Delete specific report
manager.delete("20232024", "ES", 2023020001)

# Or manually delete directories
# rm -rf data/html/20222023
```

### Git Ignore

This directory is excluded from version control via `.gitignore`. Raw HTML files are too large and change frequently to be committed to git.

## Validation Workflow

See [Issue #205](https://github.com/cooneycw/NHL-API/issues/205) for the complete JSON vs HTML validation workflow that uses these persisted reports.

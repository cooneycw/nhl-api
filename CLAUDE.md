# NHL API Project

## Before You Start - Session Checklist

- [ ] **Working directory is main repo** (`/home/cooneycw/Projects/nhl-api`)
- [ ] **NOT in a worktree directory** (e.g., `nhl-api-issue-5`)

> **Why?** Starting Claude Code from a worktree that later gets removed breaks the entire shell session. Always launch from the main repo.

---

## Claude Power Pack Integration

This project uses Claude Power Pack. Available commands:

- `/load-best-practices` - Load community wisdom
- `/github:*` - Issue management commands
- `/django:worktree-*` - Git worktree workflows (for parallel issue development)

Use second-opinion MCP for code review when needed.

### Session Coordination

Multi-session locking prevents conflicts when running parallel Claude Code sessions:

```bash
# Check active locks and sessions
~/.claude/scripts/session-lock.sh list
~/.claude/scripts/session-register.sh status

# Run pytest with coordination (prevents test interference)
~/.claude/scripts/pytest-locked.sh -m unit --no-cov
```

**Key locks:**
- `pytest-nhl-api` - Coordinates test runs across sessions
- `pr-nhl-api-*` - Prevents duplicate PR creation
- `merge-nhl-api-main` - Coordinates merges to main

See [ISSUE_DRIVEN_DEVELOPMENT.md](../claude-power-pack/ISSUE_DRIVEN_DEVELOPMENT.md) in claude-power-pack for full documentation.

## Project-Specific Commands

| Command | Purpose |
|---------|---------|
| `/nhl-next` | Scan issues, worktrees, and **active sessions** to recommend next steps (Plan Mode) |
| `/nhl-lite` | Quick project reference with session coordination status (~500 tokens) |
| `/viewer` | Start NHL Data Viewer (`--full` for frontend, `--stop` to stop) |

---

## Data Viewer

The project includes a FastAPI backend + React frontend for exploring downloaded NHL data.

### Quick Start

```bash
# Start backend only (recommended for API exploration)
./scripts/start-viewer.sh

# Start backend + frontend
./scripts/start-viewer.sh --full

# Stop all viewer processes
./scripts/start-viewer.sh --stop

# Check status
./scripts/start-viewer.sh --status
```

### URLs

| URL | Description |
|-----|-------------|
| **http://localhost:5173** | **Frontend UI** - Main dashboard |
| **http://localhost:5173/downloads** | **Downloads page** - Trigger & monitor downloads |
| http://localhost:8000/docs | Swagger UI - Interactive API explorer |
| http://localhost:8000/redoc | ReDoc API documentation |
| http://localhost:8000/health | Health check endpoint |
| http://localhost:8000/api/v1/players | Player data |
| http://localhost:8000/api/v1/teams | Team data |
| http://localhost:8000/api/v1/games | Game data |
| http://localhost:8000/api/v1/monitoring/dashboard | Download progress dashboard (API) |

Note: Frontend URLs (5173) require `--full` flag.

### Logs

```bash
# Backend logs
tail -f /tmp/nhl-viewer-backend.log

# Frontend logs
tail -f /tmp/nhl-viewer-frontend.log
```

### Requirements

- Database credentials configured in `.env` (see `.env.example`):
  - **Option 1 (local dev):** Set `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
  - **Option 2 (AWS):** Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `NHL_DB_SECRET_ID`
- Data in the database (run downloaders first to populate)

### Claude Session Usage

Use the `/viewer` command:
```
/viewer          # Start backend only
/viewer --full   # Start backend + frontend (recommended)
/viewer --stop   # Stop viewer
/viewer --status # Check status
```

Then browse to:
- http://localhost:5173/downloads - Download UI (with `--full`)
- http://localhost:8000/docs - API explorer

### Troubleshooting

**"Unable to locate credentials":**
- Ensure `.env` file exists with either `DB_*` or `AWS_*` credentials
- Copy from `.env.example` if needed

**Empty data:**
- Run downloaders first (Schedule, Boxscore, etc.) to populate the database

## Project Goals

- Consolidate NHL data pulling from existing cooneycw repos
- Future integration with oneNinety dashboard

## Existing Repos to Reference

- cooneycw/NHL
- cooneycw/nhl_apishift_v2
- cooneycw/nhl_apishift
- cooneycw/nhl_apimdc (MDC query files)
- cooneycw/nhl_apidata
- cooneycw/nhl_dailyfaceoff
- cooneycw/nhl_statsroutine
- cooneycw/nhl_quantdata
- cooneycw/NHLapiV3
- cooneycw/NHLstats

## Key Conventions

- Python 3.11+
- Use uv for environment management (`uv sync --all-extras`)
- Git worktrees for parallel issue development
- Pre-commit hooks block commits if unit tests fail
- 80% test coverage threshold

## Git Worktree Workflow

Worktrees allow parallel development on multiple issues without branch switching.

### ⚠️ Claude Code Session Warning

**ALWAYS start Claude Code sessions from the main repo directory**, not from worktree directories:

```bash
# CORRECT - start from main repo
cd /home/cooneycw/Projects/nhl-api
claude

# WRONG - starting from worktree breaks shell when worktree is removed
cd /home/cooneycw/Projects/nhl-api-issue-5
claude
```

**Why:** If Claude Code's working directory is a worktree that gets removed during cleanup, the shell session breaks completely and no bash commands can run.

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Branch | `issue-{number}-{short-description}` | `issue-5-pytest-config` |
| Worktree directory | `nhl-api-issue-{number}` | `nhl-api-issue-5` |

### Commands

**Create worktree for an issue:**
```bash
cd /home/cooneycw/Projects/nhl-api
git worktree add -b issue-{n}-{description} ../nhl-api-issue-{n}
cd ../nhl-api-issue-{n}
```

**List all worktrees:**
```bash
git worktree list
```

**Remove worktree after PR merge:**
```bash
git worktree remove ../nhl-api-issue-{n}
git branch -d issue-{n}-{description}
```

### Workflow Example

```bash
# Start work on issue #5
git worktree add -b issue-5-pytest-config ../nhl-api-issue-5
cd ../nhl-api-issue-5

# ... make changes, commit, push ...
git push -u origin issue-5-pytest-config

# Create PR, get review, merge

# Cleanup after merge
cd ../nhl-api
git worktree remove ../nhl-api-issue-5
git branch -d issue-5-pytest-config
git pull  # get merged changes
```

### Benefits

- Work on multiple issues simultaneously in separate terminals
- No `git stash` / `git checkout` needed
- Each worktree has its own working directory
- Shared git history across all worktrees
- Ideal for parallel Claude Code sessions

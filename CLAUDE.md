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

## Project-Specific Commands

- `/nhl-next` - Scan GitHub issues and worktree state, recommend prioritized next steps (uses Plan Mode)
- `/viewer` - Start the NHL Data Viewer backend (add `--full` for frontend, `--stop` to stop)

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
| http://localhost:8000/docs | **Swagger UI** - Interactive API explorer |
| http://localhost:8000/redoc | ReDoc API documentation |
| http://localhost:8000/health | Health check endpoint |
| http://localhost:8000/api/v1/players | Player data |
| http://localhost:8000/api/v1/teams | Team data |
| http://localhost:8000/api/v1/games | Game data |
| http://localhost:8000/api/v1/monitoring/dashboard | Download progress dashboard |
| http://localhost:5173 | Frontend UI (with `--full` flag) |

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
/viewer          # Start backend
/viewer --full   # Start backend + frontend
/viewer --stop   # Stop viewer
```

Then browse to http://localhost:8000/docs to explore the API interactively.

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
- Use conda environments
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

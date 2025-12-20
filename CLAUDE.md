# NHL API Project

## Claude Power Pack Integration

This project uses Claude Power Pack. Available commands:

- `/load-best-practices` - Load community wisdom
- `/github:*` - Issue management commands
- `/django:worktree-*` - Git worktree workflows (for parallel issue development)

Use second-opinion MCP for code review when needed.

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

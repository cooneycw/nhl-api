# Contributing to NHL API

Thank you for your interest in contributing to the NHL API project. This guide covers the development workflow, code standards, and pull request process.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (for environment and dependency management)
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/cooneycw/nhl-api.git
   cd nhl-api
   ```

2. **Install uv (if needed):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Create the environment and install dependencies:**
   ```bash
   uv sync --all-extras
   ```

4. **Verify installation:**
   ```bash
   uv run python -c "import nhl_api; print('nhl_api imported successfully')"
   ```

5. **Install pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```
   This installs hooks for ruff (linting/formatting), mypy (type checking), and pytest (unit tests).

## Git Worktree Workflow

This project uses git worktrees for parallel issue development. Worktrees allow working on multiple issues simultaneously without branch switching or stashing changes.

For comprehensive worktree documentation, see [CLAUDE.md](CLAUDE.md).

### Quick Reference

**Create a worktree for an issue:**
```bash
cd /path/to/nhl-api
git worktree add -b issue-{n}-{description} ../nhl-api-issue-{n}
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

### Important Warning

Always start development sessions from the **main repository directory**, not from a worktree directory. If a worktree is removed while it's your working directory, shell sessions may break.

## Branch and Commit Conventions

### Branch Naming

Use the pattern: `issue-{number}-{short-description}`

Examples:
- `issue-5-pytest-config`
- `issue-11-contributing`
- `issue-15-api-client`

### Commit Messages

- Write clear, descriptive commit messages
- Reference the issue number in your commits: `Add CONTRIBUTING.md (#11)`
- Keep the first line under 72 characters
- Use present tense: "Add feature" not "Added feature"

### Pre-Commit Requirements

All unit tests must pass before committing. This is enforced by pre-commit hooks that run automatically on each commit:

- **ruff**: Linting and auto-fixing
- **ruff-format**: Code formatting
- **mypy**: Type checking
- **pytest**: Unit tests (commit blocked if tests fail)

## Code Quality Requirements

This project enforces strict code quality standards.

### Testing with pytest

**Minimum coverage threshold: 80%**

Run tests:
```bash
# Run all tests with coverage
pytest

# Run only unit tests
pytest -m unit

# Run with HTML coverage report
pytest --cov-report=html
```

Available test markers:
- `@pytest.mark.unit` - Fast tests with no external dependencies
- `@pytest.mark.integration` - Tests requiring external services
- `@pytest.mark.data_validation` - Data integrity verification tests

### Linting with Ruff

```bash
# Check for linting errors
ruff check .

# Auto-fix fixable errors
ruff check --fix .

# Format code
ruff format .

# Check formatting without changes
ruff format --check .
```

Configuration:
- Line length: 88 characters
- Target Python version: 3.11+
- Rules: pycodestyle, pyflakes, isort, pep8-naming, bugbear, comprehensions, pyupgrade

### Type Checking with mypy

```bash
mypy .
```

Configuration:
- Strict mode enabled
- All functions require type hints
- No implicit `Any` types

## Pull Request Process

### Before Creating a PR

1. **Ensure all tests pass:**
   ```bash
   pytest
   ```

2. **Ensure linting passes:**
   ```bash
   ruff check .
   ruff format --check .
   ```

3. **Ensure type checking passes:**
   ```bash
   mypy .
   ```

4. **Push your branch:**
   ```bash
   git push -u origin issue-{n}-{description}
   ```

### Creating a PR

Using GitHub CLI:
```bash
gh pr create --title "Your PR title" --body "Closes #{issue-number}"
```

Or create via the GitHub web interface.

### PR Requirements

- Clear title referencing the issue
- Description explaining the changes
- All CI checks must pass (coming soon in [Issue #10](https://github.com/cooneycw/nhl-api/issues/10))
- Maintainer approval required

### After PR Merge

Clean up from the main repository directory:
```bash
cd /path/to/nhl-api
git worktree remove ../nhl-api-issue-{n}
git branch -d issue-{n}-{description}
git pull
```

## Issue Templates

When creating issues, use the appropriate template:

- **Bug Report** - For reporting bugs with reproduction steps
- **Feature Request** - For proposing new features
- **Data Issue** - For NHL data-related problems

## Questions?

If you have questions about contributing, open an issue or refer to the project documentation in [CLAUDE.md](CLAUDE.md).

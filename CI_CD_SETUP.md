# CI/CD Pipeline Setup

This document describes the continuous integration and deployment pipeline for ShopMindAI.

## Overview

The project uses a **hybrid CI/CD approach** combining **GitHub Actions** and **CircleCI** to ensure code quality on every push:

- **GitHub Actions** (`.github/workflows/ci.yml`): Primary CI pipeline
- **CircleCI** (`.circleci/config.yml`): Secondary checks + artifact storage + nightly runs

Both systems work in parallel to provide comprehensive checks before code reaches the main branch.

## What Gets Checked on Every Push

### 1. **Tests** (35+ unit + integration tests)
- Minimum code coverage: **85%**
- All tests must pass
- Coverage report uploaded to Codecov
- Test results posted to PR

### 2. **Database Migrations**
- All pending migrations applied successfully
- Database schema integrity verified
- Migration history validated

### 3. **Code Formatting & Linting**
- **Black**: Code formatting consistency
- **isort**: Import statement ordering
- **Ruff**: Fast linting checks
- **Pylint**: Detailed code quality analysis (threshold: 8.0/10)
- **mypy**: Type hint checking

### 4. **Security Scanning**
- Bandit: Security vulnerability scan (runs nightly)

## GitHub Actions Workflow

### File: `.github/workflows/ci.yml`

**Triggers:**
- Push to `main` or `develop`
- Pull requests against `main` or `develop`

**Jobs (run in parallel):**

1. **tests** (15 min timeout)
   - Spin up PostgreSQL service
   - Install dependencies
   - Run pytest with coverage enforcement
   - Upload to Codecov
   - Comment PR with coverage report

2. **migrations** (10 min timeout)
   - Spin up PostgreSQL service
   - Run alembic upgrade head
   - Verify no pending migrations
   - Check schema integrity

3. **lint** (10 min timeout)
   - Check Black formatting
   - Check isort import ordering
   - Run Ruff
   - Run Pylint
   - Run mypy

4. **build-status**
   - Aggregate all job results
   - **Fail entire workflow if ANY job fails**

### Branch Protection Rules

Configure in GitHub Settings → Branches → Branch protection rules for `main`:

```
✓ Require status checks to pass before merging
  - Select: "CI - Tests, Migrations, Lint"
  
✓ Require branches to be up to date before merging

✓ Require code reviews before merging
  - Required approving reviews: 1
  - Dismiss stale pull request approvals

✓ Require CODEOWNERS review
  - (if CODEOWNERS file exists)

✓ Require status checks from required contexts:
  - tests (required)
  - migrations (required)
  - lint (required)
```

## CircleCI Workflow

### File: `.circleci/config.yml`

**Executors:**
- Docker image: Python 3.11
- PostgreSQL 15 service for DB tests

**Jobs:**

1. **test**
   - Cached dependency installation
   - Wait for PostgreSQL readiness
   - Run pytest with coverage enforcement
   - Store test results as artifacts
   - Store HTML coverage report
   - Upload to Codecov

2. **migration_check**
   - Show migration history
   - Apply pending migrations
   - Verify database at head
   - Check schema integrity

3. **lint_code**
   - Black, isort, Ruff, Pylint, mypy checks
   - GitHub-formatted output for PR comments

4. **type_check**
   - Strict type checking on critical paths
   - app/providers/, app/models.py, app/schemas.py

5. **security_scan**
   - Bandit security vulnerability scan
   - Store report as artifact

6. **code_quality**
   - Code statistics and metrics
   - Complexity analysis

**Workflows:**

- **ci-pipeline**: Main workflow (runs on every push/PR)
  - All jobs in parallel
  - `workflow_status` job waits for critical jobs

- **nightly**: Scheduled daily at 2 AM UTC
  - Tests, migrations, security scan
  - For develop and main branches only

## Local Pre-Commit Hooks

### Setup

```bash
# Install pre-commit framework
pip install pre-commit

# Set up hooks
pre-commit install

# (Optional) Run all checks on existing files
pre-commit run --all-files
```

### File: `.pre-commit-config.yaml`

Hooks automatically run before each commit:
- Black formatting
- isort import sorting
- Ruff linting
- mypy type checking

## Running Checks Locally

### Run All Tests
```bash
pytest tests/ --cov=app --cov-fail-under=85
```

### Run Specific Tests
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_circuit_breaker.py -v
```

### Run Linting
```bash
# Format code with Black
black app/ tests/ scripts/

# Sort imports with isort
isort app/ tests/ scripts/

# Check with Ruff
ruff check app/ tests/ scripts/

# Type check with mypy
mypy app/ tests/
```

### Check Migrations
```bash
# Show migration history
alembic history --verbose

# See current migration
alembic current

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Troubleshooting

### CI Failures

#### ❌ Test Coverage Below 85%
```bash
# Check coverage locally
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Write tests for uncovered code
# Add to tests/unit/ or tests/integration/
```

#### ❌ Lint Failures

**Black formatting:**
```bash
black app/ tests/ scripts/
```

**isort imports:**
```bash
isort app/ tests/ scripts/
```

**Ruff errors:**
```bash
ruff check app/ tests/ scripts/ --fix
```

#### ❌ Migration Failures
```bash
# Check migration status
alembic current

# Show pending migrations
alembic upgrade head --sql

# Verify schema
python check_db_schema.py
```

#### ❌ Type Check Failures
```bash
# Run mypy to see errors
mypy app/ tests/

# Add type hints to fix
# Use # type: ignore for external libs without stubs
```

### Debugging in CI

Check artifact downloads for:
- **GitHub Actions**: "Artifacts" section in workflow run
- **CircleCI**: "Artifacts" tab in job details

Download coverage reports:
```bash
# From CircleCI, download htmlcov/ artifact
# Open index.html in browser
```

View logs:
- **GitHub Actions**: Click job in workflow run
- **CircleCI**: Click job in pipeline

## Configuration Files

### GitHub Actions
- Location: `.github/workflows/ci.yml`
- Syntax: GitHub Actions workflow YAML
- Docs: https://docs.github.com/en/actions

### CircleCI
- Location: `.circleci/config.yml`
- Syntax: CircleCI 2.1 YAML format
- Docs: https://circleci.com/docs/

### Pre-Commit
- Location: `.pre-commit-config.yaml`
- Tool: pre-commit framework
- Docs: https://pre-commit.com/

### Project Configuration
- Location: `pyproject.toml`
- Contains: Black, isort, mypy, pylint settings
- Location: `pytest.ini`
- Contains: pytest configuration
- Location: `alembic.ini`
- Contains: Database migration settings

## Best Practices

1. **Run pre-commit before pushing**
   ```bash
   pre-commit run --all-files
   ```

2. **Run tests locally before pushing**
   ```bash
   pytest tests/ --cov=app --cov-fail-under=85
   ```

3. **Write tests for new code**
   - Minimum coverage: 85%
   - Put unit tests in `tests/unit/`
   - Put integration tests in `tests/integration/`

4. **Keep migrations clean**
   - One logical change per migration
   - Test migrations locally before pushing
   - Never edit old migrations (make new ones)

5. **Follow code style**
   - Black for formatting (100 char line length)
   - isort for imports
   - Type hints on public APIs

6. **Update dependencies carefully**
   - Run full test suite after upgrade
   - Check for breaking changes
   - Update `requirements.txt` and `pyproject.toml`

## Integration with IDE

### VS Code

Install extensions:
```
ms-python.python
ms-python.vscode-pylance
charliermarsh.ruff
```

Add to `.vscode/settings.json`:
```json
{
  "python.formatting.provider": "black",
  "python.linting.pylintEnabled": true,
  "python.linting.pylintPath": "${workspaceFolder}/.venv/bin/pylint",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  }
}
```

### PyCharm

1. Settings → Tools → Python Integrated Tools
2. Set Default Test Runner to `pytest`
3. Set Code Coverage Tool to `Coverage.py`

## Merging Code

### Prerequisites
- ✓ All CI checks passing
- ✓ PR approved (if branch protection configured)
- ✓ Branches up to date with main
- ✓ Code review completed

### Process
1. All checks pass (green checkmarks)
2. Get approval from team
3. Click "Squash and merge" (recommended) or "Merge pull request"
4. Delete branch

### After Merge
- GitHub Actions runs on `main` branch
- Deployment pipeline triggers (if configured)
- Release tags created (if auto-release configured)

## Support

For CI/CD issues:
- Check GitHub Actions logs: `.github/workflows/ci.yml`
- Check CircleCI logs: `.circleci/config.yml`
- Run checks locally first (see "Running Checks Locally" section above)
- Ask team lead or DevOps contact


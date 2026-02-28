# Contributing to ShopMindAI

Thank you for contributing to ShopMindAI! This guide explains the development workflow, CI/CD requirements, and best practices.

## Quick Start

### 1. Set Up Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/ShopMindAI.git
cd ShopMindAI

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Set up database (PostgreSQL must be running)
alembic upgrade head
```

### 2. Make Changes

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make your code changes
# ...

# Pre-commit hooks run automatically before commit
# (Black, isort, Ruff, mypy checks)
git add .
git commit -m "Description of changes"

# If hooks fail, they'll auto-fix most issues
# Review changes and commit again
```

### 3. Run Full Test Suite

```bash
# Run all tests (must pass before pushing)
pytest tests/ --cov=app --cov-fail-under=85

# Run specific test type
pytest tests/unit/ -v
pytest tests/integration/ -v
```

### 4. Push and Create PR

```bash
git push origin feature/my-feature
# Go to GitHub and create Pull Request
```

### 5. CI/CD Checks Run Automatically

- ✓ GitHub Actions runs tests, migrations, linting
- ✓ CircleCI runs parallel checks
- ✓ Codecov posts coverage report to PR
- ✓ All checks must pass before merge

## Development Workflow

### Branch Strategy

```
main (production)
 ↓ PR (protected)
develop (staging)
 ↓ feature branches
feature/*, bugfix/*, docs/*
```

**Naming conventions:**
- Features: `feature/user-auth`, `feature/search-optimization`
- Bugfixes: `bugfix/crash-on-empty-input`, `bugfix/off-by-one-error`
- Docs: `docs/update-readme`, `docs/api-documentation`
- Tests: `test/add-edge-cases`, `test/integration-coverage`

### Creating a Feature

1. **Create branch from `develop`**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/my-feature
   ```

2. **Write tests first (TDD)**
   ```bash
   # Create test file
   vim tests/unit/test_my_feature.py
   
   # Test should fail initially
   pytest tests/unit/test_my_feature.py -v
   ```

3. **Implement feature**
   ```bash
   # Write code to make test pass
   vim app/my_feature.py
   
   # Run test
   pytest tests/unit/test_my_feature.py -v
   ```

4. **Run all checks**
   ```bash
   # Test coverage must be ≥85%
   pytest tests/ --cov=app --cov-fail-under=85
   
   # Format and lint
   black app/ tests/
   isort app/ tests/
   ruff check app/ tests/ --fix
   mypy app/
   ```

5. **Commit and push**
   ```bash
   git add .
   git commit -m "feature: Add my feature

   - Brief description
   - Implementation details
   - References #123"
   
   git push origin feature/my-feature
   ```

6. **Create Pull Request**
   - Use GitHub PR template (`.github/pull_request_template.md`)
   - Reference related issues (#123)
   - Describe changes and testing
   - Request reviewers

## Code Quality Standards

### Test Requirements

- **Minimum coverage**: 85%
- **Type hints**: Required on public APIs
- **Docstrings**: Required on modules, classes, functions
- **Test organization**:
  - Unit tests in `tests/unit/`
  - Integration tests in `tests/integration/`
  - E2E tests in `tests/e2e/`

### Example Test

```python
# tests/unit/test_my_feature.py
import pytest
from app.my_feature import calculate_score


class TestCalculateScore:
    """Test score calculation logic."""
    
    def test_returns_zero_for_empty_input(self):
        """Zero score for empty input."""
        assert calculate_score([]) == 0
    
    def test_returns_sum_for_valid_input(self):
        """Sum of values for valid input."""
        assert calculate_score([1, 2, 3]) == 6
    
    def test_raises_on_negative_values(self):
        """Raises ValueError for negative values."""
        with pytest.raises(ValueError):
            calculate_score([-1, 2])
```

### Code Style

**Follow PEP 8 + Black defaults:**

```python
# Good: Type hints, docstrings, readable
def calculate_embedding_similarity(
    embedding1: list[float], 
    embedding2: list[float]
) -> float:
    """Calculate cosine similarity between embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
    
    Returns:
        Similarity score between 0 and 1
    
    Raises:
        ValueError: If embeddings have different lengths
    """
    if len(embedding1) != len(embedding2):
        raise ValueError("Embeddings must have same length")
    
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    norm1 = sum(a * a for a in embedding1) ** 0.5
    norm2 = sum(b * b for b in embedding2) ** 0.5
    
    return dot_product / (norm1 * norm2)


# Avoid: No types, unclear logic, poor naming
def sim(a, b):
    return sum(x*y for x,y in zip(a,b)) / (sum(x*x for x in a)**0.5 * sum(y*y for y in b)**0.5)
```

## Database Changes

### Adding a Migration

```bash
# Ensure database is at head
alembic current

# Create migration (generates from model changes)
alembic revision --autogenerate -m "Add user_preferences table"

# Review the generated migration
vim alembic/versions/001_add_user_preferences.py

# Test migration locally
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Verify schema
python check_db_schema.py

# Commit migration file with your changes
git add alembic/versions/001_add_user_preferences.py
git commit -m "db: Add user_preferences table"
```

### Migration Checklist

- [ ] Migration auto-generated (don't manually edit if possible)
- [ ] Tested locally (upgrade → downgrade → upgrade)
- [ ] No data loss on rollback
- [ ] Indexes added for foreign keys/search columns
- [ ] Schema verified with `check_db_schema.py`
- [ ] Committed with descriptive message

## Pre-Commit Workflow

### What Pre-Commit Does

Pre-commit hooks run **automatically before each commit**:

1. **Trailing whitespace** - removes
2. **End of file fixer** - adds newline
3. **Black** - formats code
4. **isort** - organizes imports
5. **Ruff** - finds/fixes lint issues
6. **mypy** - checks types
7. **Pylint** - code quality
8. **YAML/JSON checks** - syntax validation

### Fixing Pre-Commit Failures

Most hooks auto-fix issues. If a commit fails:

```bash
# 1. Review the changes
git diff

# 2. Review the file
vim path/to/file.py

# 3. Re-stage if changes look good
git add .

# 4. Try commit again
git commit -m "your message"
```

### Bypass (Not Recommended)

If you must bypass pre-commit (e.g., work-in-progress):

```bash
git commit --no-verify -m "WIP: debugging something"
```

**Note:** CI/CD will still check these standards, so fixes will be needed before merge.

## Running Tests Locally

### All Tests

```bash
# Run with coverage (must be ≥85%)
pytest tests/ --cov=app --cov-fail-under=85 -v

# See coverage report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

### Specific Tests

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_circuit_breaker.py -v

# Specific test function
pytest tests/unit/test_circuit_breaker.py::test_failure_resets_after_success -v

# Tests matching pattern
pytest tests/ -k "circuit" -v
```

### Debugging Failures

```bash
# Show print statements
pytest tests/unit/test_my_test.py -v -s

# Drop into debugger on failure
pytest tests/unit/test_my_test.py -v --pdb

# Show locals on failure
pytest tests/unit/test_my_test.py -v -l

# Verbose output
pytest tests/unit/test_my_test.py -vv
```

## CI/CD Pipeline

### GitHub Actions (Primary)

Runs automatically on **push to main/develop** and **pull requests**:

1. **Tests** (15 min timeout)
   - PostgreSQL service
   - pytest with coverage
   - Coverage uploaded to Codecov
   - Coverage report in PR comment

2. **Migrations** (10 min timeout)
   - Alembic upgrade head
   - Verify at migration head
   - Check schema integrity

3. **Linting** (10 min timeout)
   - Black, isort, Ruff, Pylint, mypy
   - Results posted to PR

4. **Build Status** (aggregator)
   - Fails if ANY check failed
   - **Blocks merge if failing**

### CircleCI (Secondary + Nightly)

Runs in parallel for speed and nightly for security:

**CI Pipeline (on push):**
- test, migration_check, lint_code, type_check in parallel
- Artifacts: coverage reports, test results

**Nightly Workflow (2 AM UTC daily on main/develop):**
- Security scanning (bandit)
- Migration integrity checks
- Code quality metrics

### Status Checks in PR

Each PR shows check status:

```
Checks (3/3 passing) ✓
├─ tests ✓
├─ migrations ✓
├─ lint ✓
└─ build-status ✓
```

**If any fails:**
- Red ✗ next to check
- Click "Details" to see logs
- Fix locally and push again

## Troubleshooting

### "Coverage Below 85%"

```bash
# See uncovered lines
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Write tests for red lines
vim tests/unit/test_new_feature.py
```

### "Black/isort/Ruff Failures"

```bash
# Auto-fix formatting
black app/ tests/
isort app/ tests/
ruff check app/ tests/ --fix

# Re-run tests
pytest tests/ -v
```

### "Migration Failures"

```bash
# Check current migration
alembic current

# Show migration history
alembic history --verbose

# Verify schema
python check_db_schema.py

# See what would be applied
alembic upgrade head --sql
```

### "Lint Fails in CI but Passes Locally"

```bash
# Update pre-commit hooks
pre-commit autoupdate

# Run hooks on all files
pre-commit run --all-files

# Ruff might have updated rules
pip install --upgrade ruff
```

### "Type Checking Failures"

```bash
# Run mypy locally
mypy app/ tests/

# Add type hints to fix
vim app/module.py

# Use # type: ignore for external libs
from external_lib import function  # type: ignore
```

## Pull Request Process

1. **Create PR from feature branch to develop**
   - Use PR template (auto-filled)
   - Reference related issues
   - Describe changes and testing

2. **Wait for CI checks** (5-10 minutes)
   - All checks must pass (green ✓)
   - Coverage report in PR comment
   - Linting feedback as comments

3. **Address feedback**
   - Fix any failing checks
   - Respond to code review
   - Push fixes (CI runs again)

4. **Get approval**
   - At least 1 approval required
   - Team lead must review critical changes
   - CODEOWNERS must approve if applicable

5. **Merge**
   - Click "Squash and merge" (recommended)
   - Use descriptive merge commit message
   - Delete branch after merge

## Release Process

1. **Create release PR**
   - From develop to main
   - Title: "Release v1.2.0"
   - List changes

2. **Final CI checks**
   - All checks must pass
   - Additional security scan runs

3. **Merge to main**
   - Triggers deployment pipeline
   - Creates release tag
   - Builds Docker image

4. **Deploy**
   - Staging environment updated first
   - Production deployment (if configured)

## Resources

- **GitHub Issues**: Track bugs, features, discussions
- **Discussions**: Ask questions, propose ideas
- **CI/CD Setup**: See [CI_CD_SETUP.md](CI_CD_SETUP.md)
- **API Documentation**: See [API.md](API.md)
- **Database Docs**: See `alembic/` and `check_db_schema.py`

## Code of Conduct

- Be respectful and inclusive
- Assume good intent in code reviews
- Ask questions if unclear
- Share knowledge generously

## Need Help?

- 🐛 Bug found? Create an issue with reproduction steps
- 💡 Feature idea? Discuss in Discussions first
- ❓ Question? Ask in issue or Discussions
- 📚 Documentation unclear? Update it or open issue

Welcome to the team! 🎉

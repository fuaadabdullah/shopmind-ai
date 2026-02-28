# CI/CD Troubleshooting & FAQ

Quick answers to common CI/CD issues and questions.

## Common Issues

### 1. "My PR is blocked - tests failed"

**Symptom:** PR shows red ✗ on `tests` check

**Diagnosis:**
```bash
# First, run locally to see what failed
pytest tests/ --cov=app --cov-fail-under=85 -v

# Show test output
pytest tests/unit/test_my_feature.py -v -s
```

**Common Reasons:**

#### Coverage Below 85%
```bash
# See what's not covered
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Add tests for uncovered code
vim tests/unit/test_my_feature.py

# Re-run locally
pytest tests/ --cov=app --cov-fail-under=85
```

#### Test Assertion Failed
```bash
# Run specific failing test with debug info
pytest tests/unit/test_my_test.py::test_function_name -vv -s

# Drop into debugger on failure
pytest tests/unit/test_my_test.py --pdb
```

#### Database Connection Issue
```bash
# Ensure PostgreSQL is running locally
psql postgres://test_user:test_pass@localhost:5432/test_db

# Run migrations
alembic upgrade head

# Try test again
pytest tests/integration/test_db_feature.py -v
```

**Fix & Push:**
```bash
git add tests/
git commit -m "test: Add missing test coverage"
git push origin feature/my-feature
# CI runs again automatically
```

---

### 2. "My PR is blocked - migrations failed"

**Symptom:** PR shows red ✗ on `migrations` check

**Diagnosis:**
```bash
# Check current migration status
alembic current

# Check what migration is pending
alembic upgrade head --sql

# List all migrations
alembic history --verbose
```

**Common Reasons:**

#### Migration File Syntax Error
```bash
# Check migration file for Python syntax
python -m py_compile alembic/versions/001_add_table.py

# Review the migration
vim alembic/versions/001_add_table.py
```

#### Migration Can't Apply (Schema Issue)
```bash
# Test locally
alembic downgrade -1  # Rollback last migration
alembic upgrade head  # Re-apply

# Check schema
python check_db_schema.py

# Review error logs
# Look at PostgreSQL output for constraint errors, missing columns, etc.
```

#### Not All Migrations Applied
```bash
# CI expects no pending migrations
alembic current
# Should show latest migration

# If behind, apply all
alembic upgrade head

# Verify database is at head
alembic current
```

**Fix & Push:**
```bash
# Create new migration if needed
alembic revision --autogenerate -m "Fix schema issue"

# Test it
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Commit with changes
git add alembic/versions/
git commit -m "db: Fix migration issue"
git push origin feature/my-feature
```

**Prevention:**
- Always test migrations locally before pushing
- Never manually edit migration files (create new ones)
- Include migration in same PR as schema changes

---

### 3. "My PR is blocked - lint failed"

**Symptom:** PR shows red ✗ on `lint` check, multiple problems shown

**Diagnosis:**
```bash
# Run lint locally to see all issues
black --check app/
isort --check-only app/
ruff check app/
pylint app/module.py
mypy app/
```

**Common Reasons:**

#### Black Formatting Issues
```bash
# Let Black fix formatting
black app/

# Review changes
git diff

# Re-stage and test
git add .
pytest tests/ --cov=app --cov-fail-under=85
```

#### Import Sorting (isort)
```bash
# Let isort fix imports
isort app/

# Review changes
git diff

# Verify tests still pass
pytest tests/ -v
```

#### Ruff Linting Errors
```bash
# Let Ruff auto-fix what it can
ruff check app/ --fix

# For unfixable issues, review and fix manually
ruff check app/

# Common issues:
# - Unused imports: Remove them
# - Line too long: Break into multiple lines
# - Undefined name: Check spelling or import
# - Unreachable code: Remove it or fix logic
```

#### Pylint Score Below 8.0
```bash
# Check score for module
pylint app/module.py

# Review issues:
# - Too many arguments: Reduce function params
# - Missing docstring: Add docstring
# - Line too long: Break into multiple lines
# - Unused variable: Remove or use it
```

#### Type Checking (mypy) Errors
```bash
# Run mypy to see errors
mypy app/

# Common issues:
# - Missing return type: Add -> Type annotation
# - Wrong type: Check variable/parameter type
# - Unknown type: Add import or type: ignore

# Fix examples:
def process(data: dict) -> str:  # Add return type
    """Process data."""
    return str(data)

from external_lib import function  # type: ignore  # Type stubs unavailable
```

**Fix & Push:**
```bash
# Auto-fix formatting and obvious issues
black app/
isort app/
ruff check app/ --fix

# Manually fix remaining issues
vim app/module.py

# Test locally
pytest tests/ -v
mypy app/
pylint app/

# Commit
git add .
git commit -m "style: Fix linting issues"
git push origin feature/my-feature
```

---

### 4. "Pre-commit hooks failed on my commit"

**Symptom:** `git commit` fails with "The following hooks failed"

**Diagnosis:**
```bash
# Pre-commit hooks ran and detected issues
# Hooks auto-fix formatting and simple issues
```

**Common Issues:**

#### Trailing Whitespace or EOF Issues
```bash
# Pre-commit auto-fixed these
git diff

# Review the changes (they're good)
git add .
git commit -m "your message"  # Try again
```

#### Black Formatting Failed
```bash
# Let Black fix it
black app/

# Review changes
git diff

# Re-stage and try commit again
git add .
git commit -m "your message"
```

#### Type Checking Failed
```bash
# mypy reported type errors
mypy app/

# Fix the types
vim app/module.py

# Re-stage
git add .
git commit -m "your message"
```

**To Skip Pre-Commit (Not Recommended):**
```bash
git commit --no-verify -m "WIP: debugging"
# Note: CI/CD will still check, so you'll need to fix before merge
```

---

### 5. "Codecov coverage report is missing/wrong"

**Symptom:** PR doesn't show coverage comment or shows lower coverage than local

**Diagnosis:**
```bash
# Check local coverage
pytest tests/ --cov=app --cov-report=term-missing

# Compare to CI output
# Go to GitHub Actions > workflow > tests job > look for coverage output
```

**Common Reasons:**

#### Codecov Token Missing
- GitHub Actions requires `CODECOV_TOKEN` secret (if rate-limited)
- CircleCI automatically uploads if `codecov` orb configured
- Check CI logs: `Codecov token not found` → need to add secret

#### Coverage Actually Below Threshold
```bash
# This is real - tests are needed
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Add tests for uncovered lines
vim tests/unit/test_new_feature.py
```

#### Cache Issue
- Delete local coverage cache:
  ```bash
  rm -rf .coverage htmlcov/
  pytest tests/ --cov=app --cov-fail-under=85
  ```

---

### 6. "CircleCI didn't run - no config found"

**Symptom:** CircleCI shows "No config" or doesn't trigger on push

**Diagnosis:**
```bash
# Verify file exists
ls -la .circleci/config.yml

# Check file format
head -5 .circleci/config.yml
# Should start with: version: 2.1
```

**Common Reasons:**

#### File Not Committed
```bash
# File exists locally but not in git
git status .circleci/config.yml
# Should show "nothing to commit"

# If it shows untracked, commit it
git add .circleci/config.yml
git commit -m "ci: Add CircleCI config"
git push
```

#### CircleCI Not Connected
1. Go to https://app.circleci.com
2. Click "Create Project"
3. Select repository
4. Click "Set Up Project"
5. CircleCI scans for config.yml

#### Syntax Error in config.yml
```bash
# Validate YAML syntax
python -m yaml < .circleci/config.yml

# Or check online: https://www.yamllint.com/

# Fix any syntax errors
vim .circleci/config.yml
```

**Fix:**
```bash
git add .circleci/config.yml
git commit -m "ci: Fix CircleCI config"
git push
# CircleCI should now run
```

---

### 7. "Database is not ready" in CI/CD

**Symptom:** Tests fail with `psycopg2.OperationalError: connection refused`

**Diagnosis:**
- GitHub Actions: PostgreSQL service not starting
- CircleCI: wait_for_db command not working

**Common Reasons:**

#### GitHub Actions
```bash
# Check logs: Workflow > tests job > PostgreSQL service
# Health check failing: port 5432 not responding

# Usually fixes itself with retry
# If persistent: may need to increase health check timeout
```

#### CircleCI
```bash
# Check logs: Job > wait_for_db step
# pg_isready command failing

# Try locally:
pg_isready -h localhost -p 5432
# Should show: accepting connections

# If database not running:
docker pull cimg/postgres:15
docker run -d -e POSTGRES_PASSWORD=test cimg/postgres:15
```

**Configuration Issues:**
```bash
# Check ci.yml environment variables
echo $DATABASE_URL
# Should be: postgresql://test_user:test_pass@localhost:5432/test_db

# Check CircleCI config.yml PostgreSQL image
# Should be: cimg/postgres:15
```

---

### 8. "Artifact not found in CircleCI"

**Symptom:** CircleCI job passed but htmlcov/ or reports missing

**Diagnosis:**
```bash
# Artifacts stored only if:
# 1. Job ran successfully
# 2. Artifact path configured
# 3. Files actually created

# Check job logs for artifact storage commands
```

**Common Reasons:**

#### Test Failed So Artifacts Not Stored
```bash
# Fix test first
pytest tests/ --cov=app --cov-fail-under=85 -v

# Artifacts stored only on successful job
```

#### Artifact Path Wrong
```bash
# Check .circleci/config.yml
# Should have:
# store_artifacts:
#   path: htmlcov
#   destination: htmlcov
```

---

## FAQ

### Q: How do I run tests locally with same settings as CI?

**A:** Run exactly what CI runs:
```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests with coverage enforcement
pytest tests/ --cov=app --cov-fail-under=85 -v

# Check linting
black --check app/
isort --check-only app/
ruff check app/
mypy app/
```

---

### Q: Can I merge if CI is still running?

**A:** No. GitHub prevents merge while checks are running.
- Wait for all checks to complete
- If any fail: Fix → Push → CI runs again
- If all pass: Merge button becomes available

---

### Q: How long do CI checks take?

**Typical times:**
- GitHub Actions: 8-12 minutes (sequential: test + migrations + lint)
- CircleCI: 6-10 minutes (parallel jobs)
- Both together: ~12-15 minutes before PR can merge

**Optimization tips:**
- Faster tests: Use mocks, avoid DB calls in unit tests
- Faster lint: Pre-commit catches issues before push
- Parallel execution: CircleCI runs jobs simultaneously

---

### Q: What if I need to bypass CI checks?

**A:** You can't (by design). Only options:
1. **Fix the issue:** Address test/lint/migration failures properly
2. **Temporary workaround:** 
   - Commit with `--no-verify` (local only)
   - Branch protection prevents direct push to main/develop
   - CI will still check PR before merge

---

### Q: How do I know which exact test failed?

**A:** Two ways:

**In CI:**
1. Go to GitHub Actions / CircleCI dashboard
2. Click the failed job
3. Scroll to test output
4. Find the assertion that failed
5. Run locally: `pytest path/to/test.py::test_name -vv`

**Locally:**
```bash
pytest tests/ -v
# Shows which test failed: FAILED
pytest tests/unit/test_file.py::test_name -vv -s
# Shows exact error and any print statements
```

---

### Q: Why is my coverage lower in CI than locally?

**Possible reasons:**
1. **Different tests run locally** - Make sure pytest finds all tests
   ```bash
   pytest tests/ --collect-only | grep "test_" | wc -l
   ```

2. **Platform differences** - CI uses postgresql, local might use sqlite
   - Some code paths only run with PostgreSQL

3. **Environment variables** - CI might have different config
   ```bash
   # Check CI env vars in workflow config
   cat .github/workflows/ci.yml | grep -A5 "env:"
   ```

4. **Caching issue** - Clear local coverage:
   ```bash
   rm -rf .coverage htmlcov/
   pytest tests/ --cov=app --cov-fail-under=85
   ```

---

### Q: Can I view CI logs after job finishes?

**A:** Yes:

**GitHub Actions:**
1. Go to your PR
2. Click "Checks" tab
3. Click the failed check
4. View detailed logs

**CircleCI:**
1. Go to https://app.circleci.com
2. Click your project
3. Click the workflow
4. Click the failed job
5. View logs and artifacts

Logs are available for 30-90 days.

---

### Q: What if a dependency breaks my tests?

**Common scenarios:**

#### New Version of pytest Plugin
```bash
# Downgrade to known-good version
pip install pytest==7.4.0  # or similar
pytest tests/ -v
```

#### Type Stubs Missing
```bash
# mypy can't find types for dependency
# Fix by installing types package:
pip install types-dependency-name

# Or ignore in mypy:
# Create mypy.ini or add to pyproject.toml:
[mypy]
ignore_missing_imports = True
```

#### Breaking Change in Library
```bash
# Function signature changed
# Two options:

# 1. Update code to use new signature
vim app/module.py  # Update function calls

# 2. Pin to older version (temporary)
pip install library==old_version
# Add to requirements.txt with version pin
```

---

### Q: How do I update pre-commit hooks?

```bash
# See available updates
pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Test updated hooks
pre-commit run --all-files

# Commit if good
git add .pre-commit-config.yaml
git commit -m "ci: Update pre-commit hooks"
```

---

### Q: CircleCI costs - how much?

- **Free tier:** Unlimited minutes for public repos
- **Private repos:** 6,000 minutes/month free
- **Paid:** $30/month for 20,000 min, scales up
- **For ShopMindAI:** Likely within free tier

---

### Q: Why are my migrations not applying?

```bash
# Check current status
alembic current

# See what would be applied
alembic upgrade head --sql

# Test applying
alembic upgrade head

# If fails, see error
alembic upgrade head -v

# Common issues:
# 1. Syntax error in migration file
# 2. Constraint violation (can't add NOT NULL to table with NULLs)
# 3. Foreign key reference to non-existent table
# 4. Column already exists

# Fix by creating new migration:
alembic revision --autogenerate -m "Fix issue"
vim alembic/versions/...  # Edit if needed
alembic upgrade head
```

---

## Getting Help

If your issue isn't here:

1. **Check logs** (GitHub Actions / CircleCI)
2. **Run locally** to reproduce
3. **Search docs** (CI_CD_SETUP.md, CONTRIBUTING.md)
4. **Ask team** - post in #dev-help channel
5. **Check GitHub Issues** for similar problems

---

## Quick Reference

| Issue | Command |
|-------|---------|
| Test failed | `pytest tests/test_file.py::test_name -vv` |
| Coverage low | `pytest tests/ --cov=app --cov-report=html && open htmlcov/index.html` |
| Black formatting | `black app/` |
| isort imports | `isort app/` |
| Type errors | `mypy app/` |
| Lint issues | `ruff check app/ --fix` |
| DB migration | `alembic upgrade head` |
| Pre-commit install | `pre-commit install && pre-commit run --all-files` |


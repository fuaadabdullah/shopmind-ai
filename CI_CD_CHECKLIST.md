# CI/CD Configuration Checklist

This checklist ensures all CI/CD components are properly configured and deployed.

## Phase 1: Local Development Setup ✓

- [ ] `.pre-commit-config.yaml` created with:
  - [ ] Black, isort, Ruff, mypy hooks
  - [ ] Pylint configuration
  - [ ] YAML/JSON validation
  - [ ] File cleanup (trailing whitespace, EOF)

- [ ] Developers run pre-commit install:
  ```bash
  pre-commit install
  pre-commit run --all-files
  ```

## Phase 2: GitHub Actions CI ✓

- [ ] `.github/workflows/ci.yml` created with:
  - [ ] ✓ tests job (pytest + coverage, 85% threshold)
  - [ ] ✓ migrations job (alembic upgrade head)
  - [ ] ✓ lint job (Black, isort, Ruff, Pylint, mypy)
  - [ ] ✓ build-status job (aggregator, fails on any error)
  - [ ] ✓ PostgreSQL 15 service with health checks
  - [ ] ✓ Codecov upload with fail_ci_if_error: true
  - [ ] ✓ PR comment integration for coverage

**Deployment:**
- [ ] Commit `.github/workflows/ci.yml` to repository
- [ ] Push to GitHub → GitHub Actions runs automatically
- [ ] Check "Actions" tab in GitHub for results

**Configuration (GitHub Settings):**
- [ ] Branch protection enabled for `main`:
  - [ ] Require status checks to pass:
    - [ ] tests (required)
    - [ ] migrations (required)
    - [ ] lint (required)
  - [ ] Require branches up to date before merge
  - [ ] Require pull request reviews (1 approval)
  - [ ] Dismiss stale PR approvals
  - [ ] Require code owner reviews (if CODEOWNERS exists)

## Phase 3: CircleCI Secondary Checks ✓

- [ ] `.circleci/config.yml` created with:
  - [ ] ✓ Custom executor (python 3.11 + PostgreSQL 15)
  - [ ] ✓ Custom commands (setup_dependencies, wait_for_db)
  - [ ] ✓ test job (pytest, Codecov upload)
  - [ ] ✓ migration_check job (alembic verification)
  - [ ] ✓ lint_code job (Black, isort, Ruff, Pylint, mypy)
  - [ ] ✓ type_check job (mypy strict mode)
  - [ ] ✓ security_scan job (bandit)
  - [ ] ✓ code_quality job (metrics)
  - [ ] ✓ workflow_status job (aggregator)
  - [ ] ✓ ci-pipeline workflow (main, runs on push)
  - [ ] ✓ nightly workflow (2 AM UTC, security/migration scans)
  - [ ] ✓ Artifact storage (htmlcov/, bandit-report.json)

**Deployment:**
- [ ] Commit `.circleci/config.yml` to repository
- [ ] Push to GitHub
- [ ] Go to https://app.circleci.com
- [ ] Authorize GitHub OAuth
- [ ] Circle CI automatically detects config.yml and runs

**Configuration (CircleCI Settings):**
- [ ] Project created in CircleCI dashboard
- [ ] GitHub repo connected (OAuth)
- [ ] Environment variables set (if any):
  - [ ] CODECOV_TOKEN (optional, for upload)
  - [ ] DATABASE_URL, TEST_DATABASE_URL (if different from defaults)

## Phase 4: Merge Blocking ✓

**GitHub Actions:**
- [ ] build-status job requires all other jobs
- [ ] PR cannot merge if build-status fails
- [ ] Test: Create PR with failing test → should block merge

**CircleCI:**
- [ ] workflow_status job requires all critical jobs
- [ ] Mirrors GitHub Actions status
- [ ] Test: Trigger failure in CircleCI → GitHub shows status

## Phase 5: Code Coverage Enforcement ✓

**Local:**
- [ ] pytest configured to enforce 85% minimum:
  - [ ] `pytest.ini` has coverage config
  - [ ] `pyproject.toml` has [tool.coverage] section
  - [ ] Command: `pytest tests/ --cov=app --cov-fail-under=85`

**CI/CD:**
- [ ] GitHub Actions:
  - [ ] Runs with `--cov-fail-under=85` flag
  - [ ] Codecov integration: `fail_ci_if_error: true`
  - [ ] PR comment shows coverage diff
  
- [ ] CircleCI:
  - [ ] test job runs with coverage enforcement
  - [ ] Codecov upload included
  - [ ] htmlcov/ artifact stored

**Verification:**
- [ ] Write test that fails coverage threshold
- [ ] Commit → CI should fail with "Coverage too low"
- [ ] Add test → CI should pass

## Phase 6: Linting Enforcement ✓

**Tools Configured:**
- [ ] Black (code formatting)
  - [ ] pyproject.toml: `[tool.black]` with line-length = 100
  - [ ] Check: `black --check app/`
  
- [ ] isort (import sorting)
  - [ ] pyproject.toml: `[tool.isort]` profile = "black"
  - [ ] Check: `isort --check-only app/`
  
- [ ] Ruff (fast linting)
  - [ ] pyproject.toml: `[tool.ruff]` selected rules
  - [ ] Check: `ruff check app/`
  
- [ ] Pylint (deep analysis)
  - [ ] pyproject.toml: `[tool.pylint]` settings
  - [ ] Minimum score: 8.0
  - [ ] Check: `pylint app/`
  
- [ ] mypy (type checking)
  - [ ] pyproject.toml: `[tool.mypy]` with ignore_missing_imports = true
  - [ ] Check: `mypy app/`

**CI/CD Integration:**
- [ ] GitHub Actions: lint job runs all tools sequentially
- [ ] CircleCI: lint_code job runs all tools + type_check job
- [ ] Failures block merge: PR cannot merge if lint fails

**Verification:**
- [ ] Introduce formatting issue → `black app/` fixes it
- [ ] Introduce unsorted imports → `isort app/` fixes it
- [ ] Introduce missing type hint → `mypy app/` reports error
- [ ] All fixed files pass CI checks

## Phase 7: Migration Verification ✓

**Local:**
- [ ] Alembic configured in `alembic/` directory
- [ ] `alembic.ini` points to test database
- [ ] Commands:
  - [ ] `alembic current` → shows current migration
  - [ ] `alembic history` → shows all migrations
  - [ ] `alembic upgrade head` → applies all pending
  - [ ] `alembic downgrade -1` → rolls back one

**CI/CD:**
- [ ] GitHub Actions: migrations job
  - [ ] Runs `alembic upgrade head`
  - [ ] Verifies no pending migrations
  - [ ] Checks schema integrity
  - [ ] Fails if migrations not applied

- [ ] CircleCI: migration_check job
  - [ ] Shows migration history
  - [ ] Applies pending migrations
  - [ ] Verifies at head
  - [ ] Schema integrity check

**Verification:**
- [ ] Create new migration: `alembic revision --autogenerate -m "test"`
- [ ] Don't commit migration yet
- [ ] Local test: `alembic upgrade head` → should apply
- [ ] CI test: Create PR → migrations job should pass
- [ ] Remove migration → CI should fail

## Phase 8: Documentation ✓

- [ ] `CI_CD_SETUP.md` created with:
  - [ ] Overview of GitHub Actions + CircleCI
  - [ ] Branch protection rules configuration
  - [ ] Local testing commands
  - [ ] Troubleshooting guide
  - [ ] How to configure pre-commit

- [ ] `CONTRIBUTING.md` created with:
  - [ ] Development workflow
  - [ ] Branch naming conventions
  - [ ] Test requirements (85% coverage)
  - [ ] Code style examples
  - [ ] How to create PRs
  - [ ] CI/CD process explanation
  - [ ] Troubleshooting section

- [ ] `README.md` updated with:
  - [ ] Quick start: `pre-commit install`, `pytest`, etc.
  - [ ] Link to `CONTRIBUTING.md`
  - [ ] Link to `CI_CD_SETUP.md`
  - [ ] Commands for local testing and linting

## Phase 9: Team Communication ✓

- [ ] Team notified of new CI/CD pipeline:
  - [ ] "CI checks run on every push - no manual intervention needed"
  - [ ] "Pre-commit hooks run before commit - failures are auto-fixed or reported"
  - [ ] "All checks must pass before merge"
  - [ ] "Coverage must be ≥85%"

- [ ] Onboarding documentation:
  - [ ] CONTRIBUTING.md explains everything
  - [ ] CI_CD_SETUP.md as reference
  - [ ] Link in README

- [ ] Quick reference card (post in team wiki/channel):
  ```
  Setup:  pre-commit install
  Test:   pytest tests/ --cov=app --cov-fail-under=85
  Lint:   black app/ && isort app/ && ruff check app/
  Type:   mypy app/
  DB:     alembic upgrade head
  ```

## Phase 10: Final Verification

**First PR Test:**
- [ ] Create test PR with intentional formatting issue
- [ ] GitHub Actions runs and fails on lint
- [ ] PR shows build status: red ✗
- [ ] Developer fixes issue (`black app/`)
- [ ] Push fix
- [ ] CI runs again
- [ ] All checks pass: green ✓
- [ ] PR can be merged

**Second PR Test (Coverage):**
- [ ] Create test PR WITHOUT tests for new code
- [ ] GitHub Actions runs and fails on coverage
- [ ] Coverage report shows uncovered lines
- [ ] Developer adds tests
- [ ] Coverage ≥85%
- [ ] All checks pass
- [ ] PR can be merged

**Third PR Test (Migration):**
- [ ] Create test PR with database schema change
- [ ] Create migration: `alembic revision --autogenerate -m "..."`
- [ ] GitHub Actions migrations job applies new migration
- [ ] CircleCI migration_check verifies at head
- [ ] All checks pass
- [ ] PR can be merged

## Phase 11: Production Readiness

- [ ] Main branch has branch protection enabled
- [ ] Develop branch has branch protection enabled (if using)
- [ ] CI/CD status badge added to README
- [ ] Team trained on CONTRIBUTING.md
- [ ] Issues labeled with "needs-test", "needs-migration", etc.
- [ ] PR template use documented

## Monitoring & Maintenance

**Weekly:**
- [ ] Check CircleCI nightly results
- [ ] Review any security findings (bandit)
- [ ] Monitor code coverage trends

**Monthly:**
- [ ] Update dependencies (pre-commit hooks, Python packages)
- [ ] Review lint/test statistics
- [ ] Optimize slow tests

**On Failure:**
- [ ] Document issue in CONTRIBUTING.md troubleshooting section
- [ ] Update pre-commit hooks if needed
- [ ] Communicate issue to team
- [ ] Fix root cause

## Quick Links

- GitHub Actions: `.github/workflows/ci.yml`
- CircleCI: `.circleci/config.yml`
- Pre-commit: `.pre-commit-config.yaml`
- CI/CD Docs: `CI_CD_SETUP.md`
- Contributing: `CONTRIBUTING.md`
- pytest config: `pytest.ini`
- Tool config: `pyproject.toml`

---

**Status: COMPLETE ✓**

All CI/CD components configured, tested, and documented.

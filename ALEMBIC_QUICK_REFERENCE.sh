#!/usr/bin/env bash
# Quick Alembic Reference for ShopMindAI

# ============================================================================
# ALEMBIC MIGRATION QUICK REFERENCE
# ============================================================================

# Apply migrations
alembic upgrade head                              # Apply all pending migrations
alembic upgrade +1                                # Apply next 1 migration
alembic upgrade <revision_id>                     # Upgrade to specific revision

# Rollback migrations
alembic downgrade -1                              # Rollback 1 migration
alembic downgrade base                            # Rollback all migrations

# View status
alembic current                                   # Show current revision
alembic history                                   # Show migration history
alembic branches                                  # Show branch points

# Create migrations
alembic revision --autogenerate -m "Message"     # Auto-generate from models
alembic revision -m "Message"                    # Create empty migration template

# View migration details
alembic show <revision_id>                        # Show specific migration
alembic show head                                 # Show latest migration
alembic show base                                 # Show oldest migration

# ============================================================================
# TYPICAL DEVELOPMENT WORKFLOW
# ============================================================================

# Step 1: Modify database model in app/models.py
# Step 2: Generate migration
alembic revision --autogenerate -m "Add email field to users"

# Step 3: Review generated migration
cat alembic/versions/<revision_id>_add_email_field_to_users.py

# Step 4: Test migration locally
alembic upgrade head

# Step 5: Create test migrations if needed
alembic downgrade -1                              # Test rollback
alembic upgrade head                              # Re-apply

# Step 6: Commit to git
git add alembic/versions/
git commit -m "Add migration: Add email field to users"

# ============================================================================
# PRODUCTION DEPLOYMENT
# ============================================================================

# 1. Migrations run automatically on app startup via app_factory.py
# 2. Monitor logs for migration status
# 3. If needed, manually check/apply migrations:

alembic upgrade head                              # Ensure all migrations applied
alembic current                                  # Verify current version

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Migration not found?
alembic history                                   # List all migrations

# Check if alembic_version table exists:
sqlite3 data/shopmind.db "SELECT * FROM alembic_version;"

# Offline migration (generates SQL without running):
alembic upgrade head --sql                       # View SQL that would run
alembic upgrade head --sql > migration.sql       # Save to file

# Reset database (development only!):
rm data/shopmind.db                              # Remove database
alembic upgrade head                             # Recreate with all migrations

# ============================================================================
# IMPORTANT NOTES
# ============================================================================

# - Migration files are stored in: alembic/versions/
# - Configuration is in: alembic.ini and alembic/env.py
# - Never modify migration files after they've been deployed to production
# - Always test migrations locally before committing
# - Use descriptive messages for migrations: -m "Add indexes for performance"
# - Keep migration files in git: alembic/versions/ should NOT be in .gitignore

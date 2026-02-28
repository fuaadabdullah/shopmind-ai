"""
Database configuration and session management.

Provides SQLAlchemy engine, session factory, and base model for the application.

## SQL INJECTION PROTECTION

All database queries use SQLAlchemy ORM, which automatically parameterizes
all queries and binds user input as parameters. This prevents SQL injection attacks.

IMPORTANT: Never construct SQL strings with user input using f-strings or .format().
Always use SQLAlchemy column filters like:
  - Good: db.query(Model).filter(Model.id == session_id)
  - Bad:  db.execute(f"SELECT * WHERE id = {session_id}")

For additional defense in depth, use query_utils.SafeQuery wrapper class
which validates column names and enforces parameterized access patterns.

## MIGRATIONS

This project uses Alembic for database schema versioning. Alembic tracks all
schema changes and enables repeatable, version-controlled deployments across
development, staging, and production environments.

Key files:
- alembic.ini: Configuration file (database URL, logging)
- alembic/versions/: Migration scripts (auto-generated or manual)
- alembic/env.py: Migration environment setup

Common commands:
- alembic upgrade head: Apply all pending migrations
- alembic downgrade -1: Rollback one migration
- alembic revision --autogenerate -m "description": Generate migration from model changes
- alembic current: Show current schema version
"""
import os
import subprocess
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from .logger import setup_logger

logger = setup_logger(__name__)

# Database URL from environment (default to SQLite for development)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data/shopmind.db"
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# SQL_ECHO setting: Set to 'true' in development for query debugging.
# MUST be 'false' in production to avoid logging sensitive data.
sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"

if sql_echo and os.getenv("ENVIRONMENT") == "production":
    logger.warning("SQL_ECHO enabled in production - consider disabling")

# Create engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=sql_echo
    )
else:
    # PostgreSQL or other database
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=sql_echo
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db() -> None:
    """
    Initialize database schema using Alembic migrations.
    
    Runs 'alembic upgrade head' to apply all pending migrations.
    This is the recommended way to initialize the database schema
    as it provides version control and rollback capabilities.
    
    Raises:
        RuntimeError: If migration fails
    """
    try:
        logger.info("Running database migrations with Alembic...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Alembic migration failed: {result.stderr}")
            raise RuntimeError(f"Database migration failed: {result.stderr}")
        
        logger.info("Database schema initialized successfully")
        logger.debug(f"Migration output: {result.stdout}")
    except subprocess.TimeoutExpired:
        logger.error("Database migration timed out")
        raise RuntimeError("Database migration timed out")
    except FileNotFoundError:
        logger.error("Alembic not found - ensure it's installed (pip install alembic)")
        raise RuntimeError("Alembic not installed")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

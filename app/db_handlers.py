"""
Database error handling utilities for graceful degradation.

Provides decorators, context managers, and exception handlers for database
operations. Distinguishes between different error types and returns appropriate
HTTP status codes for client error reporting.

Handles:
- Connection failures (503 Service Unavailable)
- Integrity violations (409 Conflict)
- Operational errors: timeouts, deadlocks (503 Retry-After)
- Data/validation errors (400 Bad Request)
- Unknown errors with graceful fallback (500 with logging)
"""
import functools
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import exc as sql_exc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseError(Exception):
    """Base exception for database-related errors."""


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity constraint is violated."""


class DatabaseTimeoutError(DatabaseError):
    """Raised when database operation times out."""


class DatabaseOperationalError(DatabaseError):
    """Raised for operational database errors (deadlock, connection pool exhausted)."""


def handle_db_error(exc: Exception) -> HTTPException:
    """
    Convert a database exception to an appropriate HTTPException.

    Maps database errors to meaningful HTTP responses:
    - ConnectionError, OperationalError → 503 (Service Unavailable)
    - TimeoutError → 503 (Service Unavailable, Retry-After)
    - IntegrityError → 409 (Conflict)
    - DataError, ProgrammingError → 400 (Bad Request)
    - Other → 500 (Internal Server Error)

    Args:
        exc: The database exception to handle

    Returns:
        HTTPException with appropriate status code and message
    """
    # Connection errors
    if isinstance(
        exc,
        (
            sql_exc.OperationalError,
            sql_exc.DBAPIError,
            sql_exc.ResourceClosedError,
        ),
    ):
        logger.error(f"Database connection error: {str(exc)}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable. Please try again in a moment.",
            headers={"Retry-After": "30"},  # Suggest retry after 30 seconds
        )

    # Timeout errors
    if isinstance(exc, (sql_exc.TimeoutError, TimeoutError)):
        logger.error(f"Database timeout: {str(exc)}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database query timeout. Please try again.",
            headers={"Retry-After": "10"},
        )

    # Integrity constraint violations
    if isinstance(exc, sql_exc.IntegrityError):
        logger.warning(
            f"Database integrity violation: {str(exc)}",
            exc_info=False,  # Not a system error, just constraint violation
        )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operation conflicts with existing data. Please verify your input and try again.",
        )

    # Data validation errors
    if isinstance(exc, (sql_exc.DataError, sql_exc.ProgrammingError)):
        logger.error(f"Database data error: {str(exc)}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data format for database operation.",
        )

    # Database disconnection mid-transaction
    if isinstance(exc, sql_exc.DisconnectionError):
        logger.error(f"Database disconnection during operation: {str(exc)}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection lost. Please try again.",
            headers={"Retry-After": "30"},
        )

    # Fallback for other SQLAlchemy errors
    if isinstance(exc, sql_exc.SQLAlchemyError):
        logger.error(f"Database error: {str(exc)}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred. Please try again later.",
        )

    # Fallback for non-SQLAlchemy exceptions
    logger.error(f"Unexpected error in database operation: {str(exc)}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred. Please try again later.",
    )


@contextmanager
def handle_db_context(operation_name: str = "database operation"):
    """
    Context manager for database operations with error handling.

    Usage:
        with handle_db_context("updating session"):
            session.commit()

    Args:
        operation_name: Name of operation for logging

    Raises:
        HTTPException: Converted database exception
    """
    try:
        yield
    except sql_exc.SQLAlchemyError as e:
        logger.error(f"Error during {operation_name}: {str(e)}", exc_info=True)
        raise handle_db_error(e)
    except Exception as e:
        logger.error(f"Unexpected error during {operation_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete {operation_name}.",
        ) from e


def _attempt_db_operation(
    func: Callable[..., T],
    args: Any,
    kwargs: Any,
    max_retries: int,
    retry_delay: float,
) -> T:
    """
    Attempt a database operation with retries.

    Helper to reduce complexity of db_operation decorator.
    """
    attempt = 0
    max_attempts = max_retries + 1
    last_exception = None

    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)

        except (sql_exc.TimeoutError, sql_exc.OperationalError, TimeoutError) as e:
            # Transient errors: retry with backoff
            attempt += 1
            if attempt < max_attempts:
                wait_time = retry_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"Transient database error in {func.__name__}, retrying in {wait_time:.2f}s"
                )
                time.sleep(wait_time)
                last_exception = e
            else:
                logger.error(
                    f"Database operation {func.__name__} failed after {max_attempts} attempts",
                    exc_info=True,
                )
                raise handle_db_error(e) from e

        except sql_exc.SQLAlchemyError as e:
            # Non-transient errors: fail immediately
            logger.error(f"Non-transient database error in {func.__name__}", exc_info=True)
            raise handle_db_error(e) from e

        except Exception as e:
            # Non-database exceptions: fail immediately
            logger.error(f"Unexpected error in {func.__name__}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Operation failed: {str(e)}",
            ) from e

    # Should not reach here
    if last_exception:
        raise handle_db_error(last_exception)


def db_operation(
    max_retries: int = 0,
    retry_delay: float = 0.1,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for database operations with automatic retry and error handling.

    Retries transient errors (timeouts, operational errors) with exponential backoff.
    Non-transient errors (integrity violations, data errors) are not retried.

    Args:
        max_retries: Maximum number of retries (0 = no retries)
        retry_delay: Initial delay between retries in seconds

    Returns:
        Decorated function that handles database errors gracefully

    Usage:
        @db_operation(max_retries=2, retry_delay=0.1)
        def create_feedback(db: Session, data: FeedbackRequest):
            return db.add(record)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return _attempt_db_operation(func, args, kwargs, max_retries, retry_delay)

        return wrapper

    return decorator


def ensure_db_rollback(session: Session | None) -> None:
    """
    Ensure database session is rolled back after an error.

    Safe to call even if session is None or already closed.

    Args:
        session: SQLAlchemy session to rollback
    """
    if session is not None:
        try:
            session.rollback()
        except Exception as e:
            logger.warning(f"Error rolling back session: {str(e)}")


def get_retry_after_header(exc: Exception) -> dict[str, str] | None:
    """
    Generate Retry-After header for client rate limiting guidance.

    Args:
        exc: The exception to evaluate

    Returns:
        Dict with Retry-After header if applicable, None otherwise
    """
    if isinstance(
        exc,
        (
            sql_exc.OperationalError,
            sql_exc.TimeoutError,
            sql_exc.DisconnectionError,
        ),
    ):
        return {"Retry-After": "30"}
    return None

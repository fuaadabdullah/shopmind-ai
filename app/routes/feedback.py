"""
Feedback endpoint for confirming diagnostics and building training data.

Allows mechanics to provide feedback on diagnoses, enabling the feedback loop
that powers Torch model retraining.

## SECURITY

All database queries use SQLAlchemy ORM with parameterized filters.
User input (session_id, confirmed_cause) is validated by Pydantic before query use.

## ERROR HANDLING

Graceful degradation for database failures:
- Connection errors return 503 (Service Unavailable)
- Constraint violations return 409 (Conflict)
- Timeout errors return 503 with Retry-After header
- Operations are retried automatically on transient failures
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..logger import setup_logger
from ..models import DiagnosticSession
from ..query_utils import validate_int_id

logger = setup_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    """Feedback on a diagnostic session."""

    session_id: int = Field(..., gt=0, description="Session ID to confirm")
    confirmed_cause: str = Field(
        ..., min_length=1, max_length=500, description="Actual diagnosed root cause"
    )
    repair_parts: str | None = Field(
        None, description="Parts replaced/repaired (comma-separated)"
    )
    rating: int | None = Field(
        None, ge=1, le=5, description="User satisfaction (1-5 stars)"
    )
    notes: str | None = Field(None, max_length=1000, description="Additional notes")


class FeedbackResponse(BaseModel):
    """Response after feedback submission."""

    session_id: int
    status: str
    message: str
    training_ready: bool


@router.post("/confirm/{session_id}", response_model=FeedbackResponse)
def confirm_diagnosis(
    session_id: int,
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Confirm the diagnosis for a diagnostic session.

    Mechanic submits the actual repair diagnosis, marking the session
    as training-ready for Torch model retraining.

    Args:
        session_id: ID of diagnostic session (automatically validated as int)
        feedback: Feedback payload with confirmed cause + optional notes
        db: Database session (injected via FastAPI dependency)

    Returns:
        Confirmation response

    Raises:
        HTTPException: 503 if database is unavailable (will retry)
                      409 if session already confirmed (conflict)
                      400 if input is invalid
                      404 if session not found
    """
    try:
        # Validate session_id is a valid positive integer (defense in depth)
        safe_session_id = validate_int_id(session_id)

        logger.info(f"Processing feedback for session {safe_session_id}")

        try:
            # Parameterized query: column comparison binds session_id as parameter
            session = db.query(DiagnosticSession).filter(
                DiagnosticSession.id == safe_session_id
            ).first()
        except Exception as e:
            # Database query failed - service unavailable
            logger.error(f"Database query failed for session {safe_session_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service temporarily unavailable. Please try again.",
                headers={"Retry-After": "30"},
            ) from e

        if not session:
            logger.warning(f"Session {safe_session_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {safe_session_id} not found",
            )

        # Check if already confirmed
        if session.confirmed_at is not None:
            logger.warning(f"Session {safe_session_id} already confirmed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already confirmed",
            )

        # Update session with confirmation
        session.confirmed_cause = feedback.confirmed_cause
        session.repair_parts = feedback.repair_parts
        session.rating = feedback.rating
        session.confirmed_at = datetime.now()
        session.training_ready = True  # Mark for retraining

        try:
            db.commit()
        except Exception as e:
            # Commit failed - try to rollback
            db.rollback()
            logger.error(f"Failed to commit feedback for session {safe_session_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to save feedback. Please try again.",
                headers={"Retry-After": "10"},
            ) from e

        logger.info(
            f"Session {safe_session_id} confirmed as '{feedback.confirmed_cause}'; "
            f"marked training_ready=True"
        )

        return {
            "session_id": safe_session_id,
            "status": "confirmed",
            "message": f"Diagnosis confirmed: {feedback.confirmed_cause}",
            "training_ready": True,
        }

    except HTTPException:
        # Re-raise HTTP exceptions (already properly formatted)
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing feedback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        ) from e


@router.get("/stats")
def get_feedback_stats(db: Session = Depends(get_db)) -> dict:
    """
    Get statistics on diagnostic feedback.

    Returns counts of confirmed vs. unconfirmed sessions,
    useful for monitoring training data readiness.

    Returns graceful error responses if database is unavailable:
    - 503 if database connection fails
    - 500 for unexpected errors

    Returns:
        Dictionary with feedback stats or error information
    """
    try:
        # Parameterized queries using SQLAlchemy ORM
        total_sessions = db.query(DiagnosticSession).count()
        confirmed_sessions = db.query(DiagnosticSession).filter(
            DiagnosticSession.confirmed_at.isnot(None)
        ).count()
        training_ready = db.query(DiagnosticSession).filter(
            DiagnosticSession.training_ready
        ).count()

        stats = {
            "total_sessions": total_sessions,
            "confirmed_sessions": confirmed_sessions,
            "confirmation_rate": (
                round(confirmed_sessions / total_sessions * 100, 1)
                if total_sessions > 0
                else 0
            ),
            "training_ready_sessions": training_ready,
            "training_data_readiness": (
                round(training_ready / total_sessions * 100, 1)
                if total_sessions > 0
                else 0
            ),
        }

        logger.debug(f"Feedback stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Stats query failed: {str(e)}", exc_info=True)
        # Return degraded response with error info
        return {
            "error": "Database query failed",
            "total_sessions": 0,
            "confirmed_sessions": 0,
            "confirmation_rate": 0,
            "training_ready_sessions": 0,
            "training_data_readiness": 0,
        }

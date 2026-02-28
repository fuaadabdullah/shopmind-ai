"""
Data export pipeline for Torch training.

Exports labeled diagnostic data from DiagnosticSession DB table into
feature vectors ready for ML training.

## SECURITY & ERROR HANDLING

All database queries use SQLAlchemy ORM parameterized filters.
Operations gracefully degrade on database failures:
- Exports return 0 on connection failure (non-blocking)
- Stats queries return empty object on database error
- All errors are logged for monitoring
"""
import hashlib
import logging

import pandas as pd

from ..database import SessionLocal
from ..models import DiagnosticSession

logger = logging.getLogger(__name__)


def export_training_data(output_path: str = "data/training/labeled_data.csv") -> int:
    """
    Export training-ready diagnostic sessions to CSV.

    Queries DiagnosticSession where training_ready=True and confirmed=True,
    extracts features (VIN, OBD, symptoms, confirmed_cause), and exports to CSV.

    Args:
        output_path: Path to save CSV file

    Returns:
        Number of records exported (0 if database unavailable)

    Raises:
        IOError: If file write fails

    SECURITY: All filters use SQLAlchemy ORM parameterized style (column == value).
              Boolean filter (training_ready=True) is safe from SQL injection.
              Null filter (confirmed_cause.isnot(None)) is parameterized.

    ERROR HANDLING: On database errors, returns 0 (non-blocking for training pipeline).

    Example:
        >>> count = export_training_data("data/training/labeled_data.csv")
        >>> print(f"Exported {count} training samples")
    """
    db = None
    try:
        db = SessionLocal()
        logger.info("Querying training-ready diagnostic sessions...")

        # Query labeled data using ORM filters (all parameterized)
        sessions = db.query(DiagnosticSession).filter(
            DiagnosticSession.training_ready,
            DiagnosticSession.confirmed_cause.isnot(None),
        ).all()

        if not sessions:
            logger.warning("No training-ready sessions found")
            return 0

        logger.info(f"Found {len(sessions)} labeled sessions")

        # Convert to records
        records = []
        for session in sessions:
            # Check if created_at is not None before calling isoformat
            created_at_value = None
            if session.created_at is not None:
                try:
                    created_at_value = session.created_at.isoformat()
                except (AttributeError, TypeError):
                    created_at_value = None

            record = {
                "session_id": session.id,
                "vin": session.vin,
                "make": session.make,
                "model": session.model,
                "year": session.year,
                "obd_codes": session.obd_codes or "",
                "symptoms": session.symptoms,
                "confirmed_cause": session.confirmed_cause,  # Training label
                "repair_parts": session.repair_parts or "",
                "rating": session.rating,
                "created_at": created_at_value,
            }
            records.append(record)

        # Create DataFrame and save
        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False)

        logger.info(f"Exported {len(df)} samples to {output_path}")
        return len(df)

    except Exception as e:
        # Graceful degradation: log error and return 0
        logger.error(f"Export failed (database may be unavailable): {str(e)}", exc_info=True)
        return 0
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"Error closing database session: {str(e)}")


def get_data_stats() -> dict:
    """
    Get statistics on training data availability.

    Returns gracefully with zeros if database is unavailable.

    Returns:
        Dict with counts: total_sessions, labeled_sessions, labeling_rate, top_causes
        On error, returns dict with zero values logged for monitoring

    SECURITY: All filters use SQLAlchemy ORM parameterized style.
              Queries are safe from SQL injection by design.

    ERROR HANDLING: Returns zero stats on database failure (non-blocking).
    """
    db = None
    try:
        db = SessionLocal()

        total = db.query(DiagnosticSession).count()
        labeled = db.query(DiagnosticSession).filter(
            DiagnosticSession.training_ready,
            DiagnosticSession.confirmed_cause.isnot(None),
        ).count()

        # Top causes - parameterized window function query
        cause_counts = (
            db.query(
                DiagnosticSession.confirmed_cause,
                __import__("sqlalchemy").func.count().over().label("count"),
            )
            .filter(
                DiagnosticSession.training_ready,
                DiagnosticSession.confirmed_cause.isnot(None),
            )
            .distinct()
            .limit(10)
            .all()
        )

        stats = {
            "total_sessions": total,
            "labeled_sessions": labeled,
            "labeling_rate": round(labeled / total * 100, 1) if total > 0 else 0,
            "top_causes": {str(cause): count for cause, count in cause_counts},
        }

        return stats

    except Exception as e:
        # Graceful degradation: log and return empty stats
        logger.error(f"Stats query failed (database may be unavailable): {str(e)}", exc_info=True)
        return {
            "total_sessions": 0,
            "labeled_sessions": 0,
            "labeling_rate": 0,
            "top_causes": {},
        }
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"Error closing database session during stats: {str(e)}")


def deduplicate_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate training records by (VIN, OBD, symptom_hash).

    Keeps the most recent confirmed diagnosis for each unique case.

    Args:
        df: Input DataFrame with training records

    Returns:
        Deduplicated DataFrame
    """
    logger.info(f"Deduplicating {len(df)} records...")

    # Create symptom hash for deduplication
    df["symptom_hash"] = df["symptoms"].apply(
        lambda x: hashlib.sha256(x.encode()).hexdigest()
    )

    # Group by vehicle + OBD + symptom, keep most recent
    df_sorted = df.sort_values("created_at", ascending=False)
    df_dedup = df_sorted.drop_duplicates(
        subset=["vin", "obd_codes", "symptom_hash"],
        keep="first",
    )

    logger.info(f"Deduplicated to {len(df_dedup)} records")
    return df_dedup.drop(columns=["symptom_hash"])


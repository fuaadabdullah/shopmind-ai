"""
Historical success rate tracking for diagnostic scoring.

Provides functions to query and update the historical success rate
of diagnostic causes based on confirmed repairs.
"""
import hashlib
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import RootCause
from ..logger import setup_logger

logger = setup_logger(__name__)


def symptom_hash(symptom_text: str) -> str:
    """
    Generate a deterministic hash for symptom text.
    
    Uses SHA-256 to create a consistent identifier for symptom
    text, enabling deduplication while preserving privacy.
    
    Args:
        symptom_text: The symptom description text
        
    Returns:
        Hex string of the SHA-256 hash
        
    Example:
        >>> h1 = symptom_hash("Engine misfiring at idle")
        >>> h2 = symptom_hash("engine misfiring at idle")
        >>> h1 == h2  # Case insensitive
        True
    """
    return hashlib.sha256(symptom_text.lower().encode()).hexdigest()


def extract_cause_name(text: str, metadata: dict[str, Any] | None = None) -> str:
    """
    Extract the likely cause name from document text and metadata.
    
    This is a heuristic extraction - in production, this could
    be enhanced with NER or LLM-based extraction.
    
    Args:
        text: Document text content
        metadata: Optional metadata dictionary
        
    Returns:
        Extracted cause name or "Unknown"
    """
    # Try to get from metadata first
    if metadata:
        cause = metadata.get("cause") or metadata.get("root_cause")
        if cause:
            return cause.lower().strip()
    
    # Simple heuristic: look for common cause patterns
    text_lower = text.lower()
    
    # Common diagnostic cause patterns
    patterns = [
        "vacuum leak",
        "misfire",
        "catalytic converter",
        "oxygen sensor",
        "mass air flow",
        "maf sensor",
        "fuel injector",
        "spark plug",
        "ignition coil",
        "timing belt",
        " camshaft",
        "crankshaft position sensor",
        "throttle body",
        "map sensor",
        "knock sensor",
        "egr valve",
        "pcv valve",
        "fuel pump",
        "fuel pressure regulator",
        "alternator",
        "starter",
        "battery",
        "ground connection"
    ]
    
    for pattern in patterns:
        if pattern in text_lower:
            return pattern
    
    # Fallback: use first few words
    words = text.split()[:5]
    return " ".join(words).lower().strip() if words else "Unknown"


def historical_success_rate(
    db: Session,
    make: str,
    model: str,
    year: str,
    cause: str,
    symptom_text: str
) -> float:
    """
    Calculate historical success rate for a cause given vehicle and symptoms.
    
    Queries the database to find how often a particular cause was
    confirmed for similar symptoms on the same vehicle type.
    
    Args:
        db: Database session
        make: Vehicle make (e.g., "Honda")
        model: Vehicle model (e.g., "Accord")
        year: Vehicle year (e.g., "2016")
        cause: The proposed cause name
        symptom_text: The symptom description
        
    Returns:
        Success rate between 0.0 and 1.0 (0.0 if no history)
        
    Example:
        >>> rate = historical_success_rate(db, "Honda", "Accord", "2016", "vacuum leak", "rough idle")
        >>> 0.0 <= rate <= 1.0
        True
    """
    try:
        symptom_hash_val = symptom_hash(symptom_text)
        
        # Get all records for this vehicle + symptom combination
        total_query = db.query(func.count(RootCause.id)).filter(
            RootCause.make == make,
            RootCause.model == model,
            RootCause.year == year,
            RootCause.symptom_hash == symptom_hash_val,
            RootCause.confirmed == True
        )
        
        total = total_query.scalar() or 0
        
        if total == 0:
            logger.debug(f"No historical data for {make} {model} {year}")
            return 0.0
        
        # Get count where the proposed cause was the confirmed cause
        confirmed_query = db.query(func.count(RootCause.id)).filter(
            RootCause.make == make,
            RootCause.model == model,
            RootCause.year == year,
            RootCause.symptom_hash == symptom_hash_val,
            RootCause.confirmed_cause == cause,
            RootCause.confirmed == True
        )
        
        confirmed = confirmed_query.scalar() or 0
        
        rate = confirmed / total if total > 0 else 0.0
        
        logger.debug(
            f"Historical success rate for '{cause}': "
            f"{confirmed}/{total} = {rate:.2f}"
        )
        
        return float(rate)
        
    except Exception as e:
        logger.error(f"Failed to calculate historical success rate: {str(e)}")
        return 0.0


def record_diagnostic_outcome(
    db: Session,
    make: str,
    model: str,
    year: str,
    symptom_text: str,
    proposed_cause: str,
    confirmed_cause: str | None = None,
    obd_codes: str | None = None,
    source_type: str | None = None,
    initial_confidence: float | None = None
) -> RootCause:
    """
    Record a diagnostic outcome for future learning.
    
    Stores the diagnostic result in the database to enable
    the scoring engine to learn from outcomes.
    
    Args:
        db: Database session
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
        symptom_text: The symptom description
        proposed_cause: The cause that was initially proposed
        confirmed_cause: The cause that was confirmed (if known)
        obd_codes: OBD codes involved
        source_type: Source type (tsb, manual, etc.)
        initial_confidence: Initial confidence score
        
    Returns:
        Created RootCause record
    """
    try:
        symptom_hash_val = symptom_hash(symptom_text)
        
        root_cause = RootCause(
            make=make,
            model=model,
            year=year,
            symptom_hash=symptom_hash_val,
            symptom_text=symptom_text,
            cause=proposed_cause,
            confirmed_cause=confirmed_cause or proposed_cause,
            obd_codes=obd_codes,
            source_type=source_type,
            initial_confidence=initial_confidence,
            confirmed=confirmed_cause is not None
        )
        
        db.add(root_cause)
        db.commit()
        db.refresh(root_cause)
        
        logger.info(
            f"Recorded diagnostic outcome: {make} {model} {year} - "
            f"proposed: {proposed_cause}, confirmed: {confirmed_cause}"
        )
        
        return root_cause
        
    except Exception as e:
        logger.error(f"Failed to record diagnostic outcome: {str(e)}")
        db.rollback()
        raise


def get_vehicle_history(
    db: Session,
    make: str,
    model: str,
    year: str,
    limit: int = 10
) -> list[RootCause]:
    """
    Get diagnostic history for a specific vehicle.
    
    Args:
        db: Database session
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
        limit: Maximum number of records to return
        
    Returns:
        List of RootCause records
    """
    return db.query(RootCause).filter(
        RootCause.make == make,
        RootCause.model == model,
        RootCause.year == year
    ).order_by(RootCause.created_at.desc()).limit(limit).all()


def get_cause_popularity(
    db: Session,
    make: str,
    model: str,
    year: str,
    limit: int = 10
) -> list[tuple[str, int]]:
    """
    Get the most popular causes for a vehicle.
    
    Args:
        db: Database session
        make: Vehicle make
        model: Vehicle model
        year: Vehicle year
        limit: Number of top causes to return
        
    Returns:
        List of (cause, count) tuples
    """
    from sqlalchemy import desc
    
    results = db.query(
        RootCause.confirmed_cause,
        func.count(RootCause.id).label('count')
    ).filter(
        RootCause.make == make,
        RootCause.model == model,
        RootCause.year == year,
        RootCause.confirmed == True
    ).group_by(
        RootCause.confirmed_cause
    ).order_by(
        desc('count')
    ).limit(limit).all()
    
    return [(r[0], r[1]) for r in results]

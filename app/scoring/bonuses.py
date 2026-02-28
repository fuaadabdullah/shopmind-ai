"""
Bonus scoring functions for deterministic matching.

Provides deterministic bonus scores for:
- OBD code matching
- TSB (Technical Service Bulletin) matching
"""
from typing import Any

from ..logger import setup_logger

logger = setup_logger(__name__)


def obd_code_bonus(
    query_obd_codes: list[str],
    candidate_text: str
) -> float:
    """
    Check if any query OBD codes are mentioned in candidate text.
    
    Provides a binary bonus (1.0) when an OBD code from the query
    is explicitly referenced in the candidate document.
    
    Args:
        query_obd_codes: List of OBD codes from the diagnostic request
        candidate_text: Text content of the candidate document
        
    Returns:
        1.0 if any OBD code matches, 0.0 otherwise
        
    Example:
        >>> obd_code_bonus(["P0300", "P0420"], "P0300 misfire detected")
        1.0
        >>> obd_code_bonus(["P0300"], "Catalytic converter issue")
        0.0
    """
    if not query_obd_codes or not candidate_text:
        return 0.0
    
    candidate_lower = candidate_text.lower()
    
    for code in query_obd_codes:
        # Normalize code format (remove spaces, handle various formats)
        code_normalized = code.upper().strip()
        
        # Check for exact code or with common prefixes
        if (
            code_normalized in candidate_lower or
            code_normalized.replace(" ", "") in candidate_lower or
            f"code {code_normalized}" in candidate_lower or
            f"dtc {code_normalized}" in candidate_lower
        ):
            logger.debug(f"OBD code {code} matched in candidate text")
            return 1.0
    
    return 0.0


def tsb_bonus(metadata: dict[str, Any]) -> float:
    """
    Check if the candidate is from a TSB (Technical Service Bulletin).
    
    TSBs carry structural weight as they represent manufacturer-
    recognized issues with documented solutions.
    
    Args:
        metadata: Metadata dictionary for the candidate document
        
    Returns:
        1.0 if source is TSB, 0.0 otherwise
        
    Example:
        >>> tsb_bonus({"type": "tsb"})
        1.0
        >>> tsb_bonus({"type": "manual"})
        0.0
    """
    if not metadata:
        return 0.0
    
    source_type = metadata.get("source_type", "")
    doc_type = metadata.get("type", "")
    source = metadata.get("source", "")
    
    # Check various possible field names and values
    tsb_indicators = [
        "tsb",
        "technical service bulletin",
        "service bulletin",
        "manufacturer bulletin"
    ]
    
    # Check source_type
    if source_type and source_type.lower() in tsb_indicators:
        return 1.0
    
    # Check type field
    if doc_type and doc_type.lower() in tsb_indicators:
        return 1.0
    
    # Check source field
    if source and source.lower() in tsb_indicators:
        return 1.0
    
    return 0.0


def severity_bonus(metadata: dict[str, Any]) -> float:
    """
    Apply bonus based on TSB severity level.
    
    Higher severity TSBs (safety, emissions) get higher bonuses.
    
    Args:
        metadata: Metadata dictionary for the candidate document
        
    Returns:
        Severity bonus between 0.0 and 0.5
        
    Example:
        >>> severity_bonus({"severity": "high"})
        0.5
        >>> severity_bonus({"severity": "low"})
        0.1
    """
    if not metadata:
        return 0.0
    
    severity = metadata.get("severity", "").lower()
    
    severity_scores = {
        "critical": 0.5,
        "high": 0.4,
        "medium": 0.3,
        "low": 0.1,
        "normal": 0.0
    }
    
    return severity_scores.get(severity, 0.0)


def recency_bonus(metadata: dict[str, Any]) -> float:
    """
    Apply bonus based on document recency.
    
    More recent documents may be more relevant due to
    model year updates and new technical information.
    
    Args:
        metadata: Metadata dictionary for the candidate document
        
    Returns:
        Recency bonus between 0.0 and 0.2
        
    Example:
        >>> recency_bonus({"year": "2024"})
        0.2
        >>> recency_bonus({"year": "2015"})
        0.0
    """
    if not metadata:
        return 0.0
    
    try:
        year = int(metadata.get("year", 0))
        current_year = 2026  # Hardcoded current year
        
        age = current_year - year
        
        if age <= 1:
            return 0.2
        elif age <= 3:
            return 0.15
        elif age <= 5:
            return 0.1
        elif age <= 10:
            return 0.05
        else:
            return 0.0
    except (ValueError, TypeError):
        return 0.0


def compute_all_bonuses(
    query_obd_codes: list[str],
    candidate_text: str,
    metadata: dict[str, Any]
) -> dict[str, float]:
    """
    Compute all applicable bonuses for a candidate document.
    
    Args:
        query_obd_codes: List of OBD codes from the diagnostic request
        candidate_text: Text content of the candidate document
        metadata: Metadata dictionary for the candidate document
        
    Returns:
        Dictionary of bonus scores
        
    Example:
        >>> bonuses = compute_all_bonuses(["P0300"], "P0300 misfire issue", {"type": "tsb"})
        >>> bonuses["obd"]
        1.0
        >>> bonuses["tsb"]
        1.0
    """
    return {
        "obd": obd_code_bonus(query_obd_codes, candidate_text),
        "tsb": tsb_bonus(metadata),
        "severity": severity_bonus(metadata),
        "recency": recency_bonus(metadata)
    }

"""
Central hybrid scoring engine for diagnostic ranking.

Combines semantic similarity, deterministic bonuses, and historical success
rates to produce ranked diagnostic candidates with confidence scores.
"""
from typing import Any

from sqlalchemy.orm import Session

from .similarity import compute_semantic_similarity
from .bonuses import (
    obd_code_bonus,
    tsb_bonus,
    severity_bonus,
    recency_bonus,
    compute_all_bonuses
)
from .history import historical_success_rate, extract_cause_name
from .weight_manager import get_weights
from ..logger import setup_logger

logger = setup_logger(__name__)


def confidence_label(score: float) -> str:
    """
    Get human-readable confidence label for a score.
    
    Args:
        score: Confidence score (0-100)
        
    Returns:
        Human-readable label
        
    Example:
        >>> confidence_label(85)
        'Very Likely'
        >>> confidence_label(45)
        'Possible'
    """
    if score >= 80:
        return "Very Likely"
    elif score >= 60:
        return "Likely"
    elif score >= 40:
        return "Possible"
    else:
        return "Low Probability"


def rank_diagnostics(
    query_text: str,
    make: str,
    model: str,
    year: str,
    obd_codes: list[str] | None = None,
    db: Session | None = None,
    top_k: int = 10
) -> list[dict[str, Any]]:
    """
    Rank diagnostic candidates using the hybrid scoring engine.
    
    Combines multiple signals to produce ranked diagnostic causes:
    - Semantic similarity from vector search
    - OBD code match bonus
    - TSB (Technical Service Bulletin) match bonus
    - Historical success rate from confirmed repairs
    
    Args:
        query_text: Customer symptoms and description
        make: Vehicle make (e.g., "Honda")
        model: Vehicle model (e.g., "Accord")
        year: Vehicle year (e.g., "2016")
        obd_codes: List of OBD codes (optional)
        db: Database session for historical lookups (optional)
        top_k: Number of candidates to return
        
    Returns:
        List of ranked diagnostic results with scores
        
    Example:
        >>> results = rank_diagnostics("Engine misfiring at idle", "Honda", "Accord", "2016", ["P0300"])
        >>> len(results) > 0
        True
        >>> results[0]["confidence"]
        82.5
    """
    if not query_text or not query_text.strip():
        logger.warning("Empty query text provided")
        return []
    
    # Get current scoring weights
    weights = get_weights()
    
    # Compute semantic similarity candidates
    candidates = compute_semantic_similarity(query_text, top_k=top_k)
    
    if not candidates:
        logger.warning("No candidates found from semantic search")
        return []
    
    logger.info(
        f"Ranking {len(candidates)} candidates for {make} {model} {year}"
    )
    
    # Parse OBD codes
    if obd_codes is None:
        obd_codes = []
    elif isinstance(obd_codes, str):
        obd_codes = [c.strip() for c in obd_codes.split(",") if c.strip()]
    
    # Score each candidate
    ranked = []
    
    for c in candidates:
        # Extract candidate text and metadata
        candidate_text = c.get("text", "")
        metadata = c.get("metadata", {})
        
        # Get semantic score (already computed)
        semantic = c.get("semantic_score", 0.0)
        
        # Compute deterministic bonuses
        obd_bonus = obd_code_bonus(obd_codes, candidate_text)
        tsb = tsb_bonus(metadata)
        severity = severity_bonus(metadata)
        recency = recency_bonus(metadata)
        
        # Get historical success rate if database available
        history = 0.0
        if db is not None:
            cause_name = extract_cause_name(candidate_text, metadata)
            history = historical_success_rate(
                db, make, model, year, cause_name, query_text
            )
        
        # Calculate weighted confidence score
        confidence = (
            weights["semantic"] * semantic +
            weights["tsb"] * tsb +
            weights["obd"] * obd_bonus +
            weights["history"] * history +
            weights["severity"] * severity +
            weights["recency"] * recency
        )
        
        # Convert to percentage
        confidence_pct = round(confidence * 100, 2)
        
        # Extract cause name
        cause_name = extract_cause_name(candidate_text, metadata)
        
        ranked.append({
            "cause": cause_name,
            "confidence": confidence_pct,
            "label": confidence_label(confidence_pct),
            "breakdown": {
                "semantic": round(semantic, 3),
                "tsb_match": bool(tsb),
                "obd_match": bool(obd_bonus),
                "history": round(history, 3),
                "severity": round(severity, 3),
                "recency": round(recency, 3)
            },
            "weights_used": {
                "semantic": weights["semantic"],
                "tsb": weights["tsb"],
                "obd": weights["obd"],
                "history": weights["history"],
                "severity": weights["severity"],
                "recency": weights["recency"]
            },
            "source": c.get("source", "unknown"),
            "text_preview": candidate_text[:200] + "..." if len(candidate_text) > 200 else candidate_text,
            "metadata": metadata
        })
    
    # Sort by confidence (highest first)
    ranked.sort(key=lambda x: x["confidence"], reverse=True)
    
    logger.info(f"Ranked {len(ranked)} candidates, top confidence: {ranked[0]['confidence'] if ranked else 0}")
    
    return ranked


def get_top_candidates(
    ranked_results: list[dict[str, Any]],
    min_confidence: float = 0.0,
    limit: int = 5
) -> list[dict[str, Any]]:
    """
    Filter and limit ranked candidates.
    
    Args:
        ranked_results: Full ranked results from rank_diagnostics
        min_confidence: Minimum confidence threshold (0-100)
        limit: Maximum number of candidates to return
        
    Returns:
        Filtered list of candidates
    """
    filtered = [
        r for r in ranked_results
        if r["confidence"] >= min_confidence
    ]
    
    return filtered[:limit]


def format_diagnostic_explanation(result: dict[str, Any]) -> str:
    """
    Format a diagnostic result as a human-readable explanation.
    
    Args:
        result: Single diagnostic result
        
    Returns:
        Formatted explanation string
        
    Example:
        >>> result = {"cause": "vacuum leak", "confidence": 82.5, "label": "Very Likely", "breakdown": {...}}
        >>> print(format_diagnostic_explanation(result))
        Vacuum Leak
        Confidence: 82.5% (Very Likely)
        Reason:
          Semantic Match: 0.85
          TSB Match: Yes
          OBD Match: Yes
          Historical: 0.60
    """
    lines = [
        result["cause"].title(),
        f"Confidence: {result['confidence']}% ({result['label']})",
        "Reason:",
        f"  Semantic Match: {result['breakdown']['semantic']}",
        f"  TSB Match: {'Yes' if result['breakdown']['tsb_match'] else 'No'}",
        f"  OBD Match: {'Yes' if result['breakdown']['obd_match'] else 'No'}",
        f"  Historical: {result['breakdown']['history']}"
    ]
    
    return "\n".join(lines)


def explain_ranking(
    ranked_results: list[dict[str, Any]],
    top_n: int = 3
) -> str:
    """
    Generate a detailed explanation of why candidates were ranked this way.
    
    Args:
        ranked_results: Full ranked results
        top_n: Number of top results to explain
        
    Returns:
        Formatted explanation string
    """
    if not ranked_results:
        return "No diagnostic results available."
    
    lines = ["Diagnostic Analysis", "=" * 40, ""]
    
    for i, result in enumerate(ranked_results[:top_n], 1):
        lines.append(f"{i}. {format_diagnostic_explanation(result)}")
        lines.append("")
    
    return "\n".join(lines)

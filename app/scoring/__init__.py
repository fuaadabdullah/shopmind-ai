"""
Scoring package for hybrid diagnostic ranking.

This package implements the hybrid scoring engine that combines:
- Semantic similarity (vector search)
- OBD code matching bonuses
- TSB (Technical Service Bulletin) matching
- Historical success rates from confirmed repairs
"""
from .hybrid_score import rank_diagnostics, confidence_label
from .weight_manager import get_weights, update_history_weight

__all__ = [
    "rank_diagnostics",
    "confidence_label",
    "get_weights",
    "update_history_weight",
]

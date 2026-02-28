"""
Weight manager for dynamic scoring weights.

Manages the weights used in the hybrid scoring algorithm and
provides functionality for dynamic weight adjustment based on
prediction accuracy.
"""
import os
from typing import Dict

from ..logger import setup_logger

logger = setup_logger(__name__)

# Default weights for the hybrid scoring algorithm
# These can be overridden by environment variables
DEFAULT_WEIGHTS = {
    "semantic": 0.40,      # Semantic similarity score
    "tsb": 0.20,           # TSB match bonus
    "obd": 0.15,           # OBD code match bonus
    "history": 0.15,       # Historical success rate
    "severity": 0.05,      # TSB severity bonus
    "recency": 0.05        # Document recency bonus
}

# Mutable weights storage
WEIGHTS: Dict[str, float] = DEFAULT_WEIGHTS.copy()

# Weight adjustment configuration
MIN_HISTORY_WEIGHT = 0.10
MAX_HISTORY_WEIGHT = 0.35
WEIGHT_ADJUSTMENT_STEP = 0.02


def get_weights() -> Dict[str, float]:
    """
    Get the current scoring weights.
    
    Loads weights from environment variables if available,
    otherwise returns the default weights.
    
    Returns:
        Dictionary of weight names to values
        
    Example:
        >>> weights = get_weights()
        >>> weights["semantic"]
        0.4
    """
    # Check for environment variable overrides
    for key in DEFAULT_WEIGHTS:
        env_key = f"WEIGHT_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            try:
                WEIGHTS[key] = float(env_value)
                logger.info(f"Loaded weight from env: {key} = {env_value}")
            except ValueError:
                logger.warning(f"Invalid weight value for {key}: {env_value}")
    
    return WEIGHTS.copy()


def update_weight(key: str, value: float) -> None:
    """
    Update a specific weight value.
    
    Args:
        key: Weight name
        value: New weight value (will be clamped to 0-1)
    """
    if key not in DEFAULT_WEIGHTS:
        logger.warning(f"Unknown weight key: {key}")
        return
    
    # Clamp value between 0 and 1
    WEIGHTS[key] = max(0.0, min(1.0, value))
    logger.info(f"Updated weight: {key} = {WEIGHTS[key]}")


def update_history_weight(boost_factor: float = WEIGHT_ADJUSTMENT_STEP) -> None:
    """
    Increase the history weight to give more importance to
    confirmed diagnostic outcomes.
    
    This can be called when the system detects high accuracy
    in historical predictions.
    
    Args:
        boost_factor: Amount to increase history weight by
    """
    current = WEIGHTS["history"]
    new_value = min(MAX_HISTORY_WEIGHT, current + boost_factor)
    WEIGHTS["history"] = new_value
    
    logger.info(f"Updated history weight: {current} -> {new_value}")


def decrease_history_weight(reduction_factor: float = WEIGHT_ADJUSTMENT_STEP) -> None:
    """
    Decrease the history weight when historical predictions
    are found to be inaccurate.
    
    Args:
        reduction_factor: Amount to decrease history weight by
    """
    current = WEIGHTS["history"]
    new_value = max(MIN_HISTORY_WEIGHT, current - reduction_factor)
    WEIGHTS["history"] = new_value
    
    logger.info(f"Updated history weight: {current} -> {new_value}")


def normalize_weights() -> Dict[str, float]:
    """
    Normalize weights so they sum to 1.0.
    
    Useful when weights have been adjusted and need to be
    rescaled to maintain the total weight at 100%.
    
    Returns:
        Normalized weight dictionary
    """
    total = sum(WEIGHTS.values())
    
    if total == 0:
        return WEIGHTS.copy()
    
    normalized = {k: v / total for k, v in WEIGHTS.items()}
    WEIGHTS.update(normalized)
    
    logger.debug(f"Normalized weights: {normalized}")
    return normalized


def reset_weights() -> Dict[str, float]:
    """
    Reset all weights to their default values.
    
    Returns:
        Default weight dictionary
    """
    global WEIGHTS
    WEIGHTS = DEFAULT_WEIGHTS.copy()
    logger.info("Weights reset to defaults")
    return WEIGHTS.copy()


def get_weight_config() -> Dict[str, float]:
    """
    Get the current weight configuration.
    
    Returns:
        Dictionary with current weights and limits
    """
    return {
        "weights": WEIGHTS.copy(),
        "defaults": DEFAULT_WEIGHTS.copy(),
        "limits": {
            "min_history": MIN_HISTORY_WEIGHT,
            "max_history": MAX_HISTORY_WEIGHT,
            "adjustment_step": WEIGHT_ADJUSTMENT_STEP
        }
    }


def validate_weights(weights: Dict[str, float]) -> bool:
    """
    Validate that weights are reasonable.
    
    Checks:
    - All expected keys present
    - All values between 0 and 1
    - At least some weight on semantic similarity
    
    Args:
        weights: Weight dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Check all keys present
    if not all(k in weights for k in DEFAULT_WEIGHTS):
        logger.warning("Missing weight keys")
        return False
    
    # Check all values in range
    if not all(0 <= v <= 1 for v in weights.values()):
        logger.warning("Weight values out of range")
        return False
    
    # Check semantic has at least some weight
    if weights.get("semantic", 0) < 0.1:
        logger.warning("Semantic weight too low")
        return False
    
    return True

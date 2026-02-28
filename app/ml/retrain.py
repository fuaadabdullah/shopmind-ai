"""Retraining pipeline for XGBoost model.

Scheduled job (e.g., daily cron) that:
1. Exports labeled data from DB
2. Trains new XGBoost model
3. Validates against metrics
4. Registers with auto-incremented version
5. Supports instant rollback if needed

Auto-Increment Strategy:
  - Default: Minor version bump (v1.0 → v1.1 → v1.2, etc.)
  - Optional: Major version bump (v1.0 → v2.0) for breaking changes
  - Rollback: Instantly reactivate previous version if degradation detected
"""
import logging
from datetime import datetime

from .data_prep import export_training_data, get_data_stats
from .trainer import train_model
from .registry import get_registry

logger = logging.getLogger(__name__)


def retrain_model(
    min_samples: int = 100,
    bump_type: str = "minor",
    auto_increment: bool = True,
) -> dict:
    """Trigger model retraining from labeled data.

    Can be called manually or scheduled (e.g., daily).

    Args:
        min_samples: Minimum labeled samples before retraining
        bump_type: "minor" (default) or "major" for version increment
        auto_increment: Whether to auto-calculate next version (default True)

    Returns:
        Status dict with keys: success, message, version, metrics,
                               previous_version, rollback_available, trained_at

    Example:
        >>> result = retrain_model(min_samples=500)
        >>> if result['success']:
        ...     print(f"Trained {result['version']}")
        ...     print(f"Can rollback to: {result.get('previous_version')}")
    """
    try:
        logger.info("Starting model retraining...")

        # Check data readiness
        logger.info("Checking training data availability...")
        stats = get_data_stats()
        labeled_count = stats.get("labeled_sessions", 0)

        if labeled_count < min_samples:
            logger.warning(
                f"Insufficient labeled data: {labeled_count} < {min_samples}"
            )
            return {
                "success": False,
                "message": f"Need {min_samples - labeled_count} more labeled samples",
                "labeled_sessions": labeled_count,
            }

        # Export training data
        logger.info(f"Exporting {labeled_count} labeled sessions...")
        csv_path = "data/training/labeled_data.csv"
        export_training_data(csv_path)

        # Train model
        logger.info("Training XGBoost classifier...")
        model, encoder, metrics = train_model(csv_path, save_model=True)

        logger.info(f"Training complete. Metrics: {metrics}")

        # Get previous version before registering new one
        registry = get_registry()
        previous_version = registry.get_active_version()

        # Register model with auto-increment
        version = registry.register_model(
            version=None,  # Auto-calculate next version
            accuracy=metrics["accuracy"],
            precision=metrics.get("precision", {}),
            recall=metrics.get("recall", {}),
            samples_used=int(metrics.get("n_training_samples", 0)),
            auto_increment=auto_increment,
            bump_type=bump_type,
        )

        logger.info(f"Model {version} registered and ready for serving")

        if previous_version:
            logger.info(f"Version transition: {previous_version} → {version}")

        return {
            "success": True,
            "message": f"Model {version} trained successfully",
            "version": version,
            "metrics": metrics,
            "previous_version": previous_version,
            "rollback_available": previous_version is not None,
            "trained_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Retraining failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Retraining failed: {str(e)}",
            "error": str(e),
        }


def trigger_rollback() -> dict:
    """Instantly rollback to the previous model version.

    Useful if the new model has degraded performance or encountered errors.

    Returns:
        Status dict with keys: success, message, rolled_back_to, error (if any)

    Example:
        >>> result = trigger_rollback()
        >>> if result['success']:
        ...     print(f"Rolled back to {result['rolled_back_to']}")
    """
    try:
        logger.info("Initiating model rollback...")

        registry = get_registry()
        rolled_back_to = registry.rollback_to_previous()

        if rolled_back_to:
            logger.info(f"Successfully rolled back to {rolled_back_to}")
            return {
                "success": True,
                "message": f"Rolled back to {rolled_back_to}",
                "rolled_back_to": rolled_back_to,
            }
        else:
            logger.warning("No previous version available for rollback")
            return {
                "success": False,
                "message": "No previous version available",
                "rolled_back_to": None,
            }

    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Rollback failed: {str(e)}",
            "error": str(e),
        }


if __name__ == "__main__":
    # Can be run standalone: python -m app.ml.retrain
    logging.basicConfig(level=logging.INFO)
    result = retrain_model(min_samples=100)
    logger.info(f"Retrain result: {result}")

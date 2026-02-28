"""ML model registry and metadata management.

Tracks model versions, training metrics, enables version-based serving,
and handles automatic version incrementing with rollback support.

Version Format: Semantic versioning (v1.0, v1.1, v2.0)
  - Major: Breaking changes to model architecture
  - Minor: Normal retraining with improved metrics
  - Auto-increment: Minor version increases by default on retrain
  - Rollback: Point to previous version for instant fallback
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ML_REGISTRY_PATH

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Track ML model versions with auto-increment and rollback."""

    def __init__(self, path: str = ML_REGISTRY_PATH):
        """Initialize model registry."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        """Load registry from disk or create new."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data: dict[str, Any] = json.load(f)
                    return data
            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")
                return {}
        return {}

    def _save_registry(self) -> None:
        """Save registry to disk."""
        with open(self.path, "w") as f:
            json.dump(self.registry, f, indent=2, default=str)

    def _parse_version(self, version: str) -> tuple[int, int]:
        """Parse semantic version string to (major, minor) tuple.

        Args:
            version: Version string like "v1.0" or "v2.3"

        Returns:
            Tuple of (major, minor) as integers

        Raises:
            ValueError: If version format is invalid
        """
        if not version.startswith("v"):
            raise ValueError(f"Version must start with 'v': {version}")

        try:
            parts = version[1:].split(".")
            if len(parts) != 2:
                raise ValueError(f"Version must be semantic (v1.0): {version}")
            major, minor = int(parts[0]), int(parts[1])
            return major, minor
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid version format '{version}': {e}") from e

    def _format_version(self, major: int, minor: int) -> str:
        """Format (major, minor) tuple to version string."""
        return f"v{major}.{minor}"

    def get_next_version(self, bump_type: str = "minor") -> str:
        """Calculate next version based on current models.

        Args:
            bump_type: "minor" (default) or "major"

        Returns:
            Next version string (e.g., "v1.1" or "v2.0")
        """
        versions = self.list_models()

        if not versions:
            # First version
            return "v1.0"

        # Get highest version
        try:
            latest = versions[0]
            major, minor = self._parse_version(latest)

            if bump_type == "major":
                return self._format_version(major + 1, 0)
            elif bump_type == "minor":
                return self._format_version(major, minor + 1)
            else:
                raise ValueError(f"Unknown bump type: {bump_type}")
        except ValueError as e:
            logger.error(f"Failed to parse latest version: {e}")
            return "v1.0"

    def register_model(
        self,
        version: str | None = None,
        accuracy: float | None = None,
        precision: dict[str, float] | None = None,
        recall: dict[str, float] | None = None,
        samples_used: int | None = None,
        auto_increment: bool = True,
        bump_type: str = "minor",
    ) -> str:
        """Register a trained model.

        Args:
            version: Model version (e.g., "v1.0"). If None and auto_increment=True,
                     automatically calculates next version.
            accuracy: Overall accuracy on test set
            precision: Per-class precision scores
            recall: Per-class recall scores
            samples_used: Number of training samples
            auto_increment: If True and version=None, auto-calculate next version
            bump_type: "minor" (default) or "major" for version increment

        Returns:
            The registered version string
        """
        # Auto-increment version if not provided
        if version is None:
            if auto_increment:
                version = self.get_next_version(bump_type=bump_type)
            else:
                raise ValueError("version must be provided if auto_increment=False")

        # Validate version format
        try:
            self._parse_version(version)
        except ValueError as e:
            raise ValueError(f"Invalid version format: {e}")

        # Mark previous version as inactive and set rollback pointer
        old_active = self.get_active_version()
        if old_active and old_active in self.registry:
            self.registry[old_active]["status"] = "inactive"
            self.registry[old_active]["superseded_by"] = version

        # Register new version
        self.registry[version] = {
            "version": version,
            "trained_at": datetime.utcnow().isoformat(),
            "accuracy": accuracy,
            "precision": precision or {},
            "recall": recall or {},
            "samples_used": samples_used,
            "status": "active",
            "superseded_by": None,
        }

        self._save_registry()
        logger.info(
            f"Registered model {version} with accuracy {accuracy:.2%} "
            f"(status: active)"
        )

        return version

    def get_active_version(self) -> str | None:
        """Get the currently active model version for serving."""
        for version in reversed(self.list_models()):
            model_info = self.registry.get(version, {})
            if model_info.get("status") == "active":
                return version
        return None

    def rollback_to_previous(self) -> str | None:
        """Rollback to the previous version.

        Useful if the new model has degraded performance or failed validation.

        Returns:
            The version rolled back to, or None if no previous version
        """
        active = self.get_active_version()
        if not active:
            logger.warning("No active version to rollback from")
            return None

        # Find version that was superseded by current active version
        for version, info in self.registry.items():
            if (
                info.get("superseded_by") == active
                and info.get("status") != "deleted"
            ):
                # Reactivate previous version
                self.registry[active]["status"] = "inactive"
                self.registry[version]["status"] = "active"
                self._save_registry()

                logger.info(f"Rolled back from {active} to {version}")
                return version

        logger.warning("No previous version found to rollback to")
        return None

    def get_model_info(self, version: str | None = None) -> dict[str, Any]:
        """Get metadata for a model version.

        Args:
            version: Specific version to get, or None for active version

        Returns:
            Dict with model metadata or empty dict if not found
        """
        if version is None:
            version = self.get_active_version()

        if version is None:
            return {}

        result: dict[str, Any] = self.registry.get(version, {})
        return result

    def list_models(self) -> list[str]:
        """List all registered model versions (sorted, newest first)."""
        try:
            return sorted(
                self.registry.keys(),
                key=lambda v: self._parse_version(v),
                reverse=True,
            )
        except ValueError:
            # Fallback to string sorting if version parsing fails
            return sorted(self.registry.keys(), reverse=True)

    def get_latest_version(self) -> str | None:
        """Get the most recent model version (not necessarily active)."""
        versions = self.list_models()
        return versions[0] if versions else None

    def deprecate_model(self, version: str) -> None:
        """Mark a model as deprecated (old, not recommended)."""
        if version in self.registry:
            self.registry[version]["status"] = "deprecated"
            self._save_registry()
            logger.info(f"Deprecated model {version}")

    def delete_model(self, version: str) -> None:
        """Delete a model version from registry."""
        if version in self.registry:
            self.registry[version]["status"] = "deleted"
            self._save_registry()
            logger.info(f"Deleted model {version}")

    def compare_versions(self, v1: str, v2: str) -> dict[str, Any]:
        """Compare two model versions side-by-side.

        Args:
            v1, v2: Version strings to compare

        Returns:
            Dict with comparison metrics (accuracy, samples, etc.)
        """
        info1 = self.get_model_info(v1)
        info2 = self.get_model_info(v2)

        if not info1 or not info2:
            return {}

        return {
            "v1": v1,
            "v2": v2,
            "v1_accuracy": info1.get("accuracy"),
            "v2_accuracy": info2.get("accuracy"),
            "accuracy_delta": info2.get("accuracy", 0) - info1.get("accuracy", 0),
            "v1_samples": info1.get("samples_used"),
            "v2_samples": info2.get("samples_used"),
            "v1_trained": info1.get("trained_at"),
            "v2_trained": info2.get("trained_at"),
        }


# Global registry instance
_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    """Get or initialize the model registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry

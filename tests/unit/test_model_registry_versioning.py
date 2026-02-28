"""Unit tests for model registry versioning functionality.

Tests semantic versioning, auto-increment, active tracking, and rollback.
"""
import json

import pytest

from app.ml.registry import ModelRegistry


@pytest.fixture
def temp_registry(tmp_path):
    """Create a temporary registry for testing."""
    registry_path = tmp_path / "registry.json"
    registry = ModelRegistry(path=str(registry_path))
    return registry, registry_path


class TestVersionParsing:
    """Test semantic version parsing and formatting."""

    def test_parse_valid_version(self, temp_registry):
        """Parse valid semantic version."""
        registry, _ = temp_registry
        major, minor = registry._parse_version("v1.0")
        assert major == 1
        assert minor == 0

    def test_parse_version_with_double_digits(self, temp_registry):
        """Parse version with double-digit numbers."""
        registry, _ = temp_registry
        major, minor = registry._parse_version("v10.25")
        assert major == 10
        assert minor == 25

    def test_parse_invalid_version_format(self, temp_registry):
        """Reject invalid version format."""
        registry, _ = temp_registry
        with pytest.raises(ValueError, match="Version must start with"):
            registry._parse_version("1.0")  # Missing 'v'

    def test_format_version(self, temp_registry):
        """Format (major, minor) tuple to version string."""
        registry, _ = temp_registry
        assert registry._format_version(1, 0) == "v1.0"
        assert registry._format_version(2, 5) == "v2.5"


class TestAutoIncrement:
    """Test automatic version incrementing logic."""

    def test_first_version_empty_registry(self, temp_registry):
        """First version should be v1.0 for empty registry."""
        registry, _ = temp_registry
        assert registry.get_next_version() == "v1.0"

    def test_minor_version_bump(self, temp_registry):
        """Minor version bump: v1.0 → v1.1."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        next_v = registry.get_next_version(bump_type="minor")
        assert next_v == "v1.1"

    def test_major_version_bump(self, temp_registry):
        """Major version bump: v1.0 → v2.0."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        next_v = registry.get_next_version(bump_type="major")
        assert next_v == "v2.0"

    def test_auto_increment_with_registration(self, temp_registry):
        """Register model with auto-increment enabled."""
        registry, _ = temp_registry
        v1 = registry.register_model(
            accuracy=0.85,
            samples_used=100,
            auto_increment=True,
            bump_type="minor",
        )
        assert v1 == "v1.0"

        # Next registration auto-increments
        v2 = registry.register_model(
            accuracy=0.90,
            samples_used=150,
            auto_increment=True,
            bump_type="minor",
        )
        assert v2 == "v1.1"


class TestActiveVersion:
    """Test active version tracking."""

    def test_first_registered_is_active(self, temp_registry):
        """First registered version is immediately active."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        assert registry.get_active_version() == "v1.0"

    def test_new_version_becomes_active(self, temp_registry):
        """New registered version becomes active."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        registry.register_model(
            version="v1.1",
            accuracy=0.90,
            samples_used=150,
            auto_increment=False,
        )
        assert registry.get_active_version() == "v1.1"

    def test_no_active_version_in_empty_registry(self, temp_registry):
        """Empty registry has no active version."""
        registry, _ = temp_registry
        assert registry.get_active_version() is None


class TestRollback:
    """Test rollback to previous version."""

    def test_rollback_to_previous(self, temp_registry):
        """Rollback from v1.1 to v1.0."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        registry.register_model(
            version="v1.1",
            accuracy=0.90,
            samples_used=150,
            auto_increment=False,
        )

        assert registry.get_active_version() == "v1.1"

        # Rollback
        rolled_back = registry.rollback_to_previous()
        assert rolled_back == "v1.0"
        assert registry.get_active_version() == "v1.0"

    def test_rollback_marks_old_version_inactive(self, temp_registry):
        """Rollback marks previous active version as inactive."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        registry.register_model(
            version="v1.1",
            accuracy=0.90,
            samples_used=150,
            auto_increment=False,
        )

        registry.rollback_to_previous()

        assert registry.get_model_info("v1.0")["status"] == "active"
        assert registry.get_model_info("v1.1")["status"] == "inactive"

    def test_rollback_no_previous_version(self, temp_registry):
        """Rollback fails gracefully with no previous version."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )

        # Only one version, no previous
        result = registry.rollback_to_previous()
        assert result is None


class TestVersionComparison:
    """Test version comparison utility."""

    def test_compare_accuracy_improvement(self, temp_registry):
        """Compare metrics between two versions."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        registry.register_model(
            version="v1.1",
            accuracy=0.90,
            samples_used=150,
            auto_increment=False,
        )

        comparison = registry.compare_versions("v1.0", "v1.1")
        assert comparison["v1_accuracy"] == 0.85
        assert comparison["v2_accuracy"] == 0.90
        assert comparison["accuracy_delta"] == pytest.approx(0.05)


class TestVersionList:
    """Test version listing and sorting."""

    def test_list_sorted_newest_first(self, temp_registry):
        """Models listed with newest first."""
        registry, _ = temp_registry
        registry.register_model(version="v1.0", accuracy=0.85, samples_used=100, auto_increment=False)
        registry.register_model(version="v1.1", accuracy=0.90, samples_used=150, auto_increment=False)
        registry.register_model(version="v2.0", accuracy=0.92, samples_used=200, auto_increment=False)

        versions = registry.list_models()
        assert versions == ["v2.0", "v1.1", "v1.0"]

    def test_get_latest_version(self, temp_registry):
        """Get latest (not necessarily active) version."""
        registry, _ = temp_registry
        registry.register_model(version="v1.0", accuracy=0.85, samples_used=100, auto_increment=False)
        registry.register_model(version="v1.1", accuracy=0.90, samples_used=150, auto_increment=False)

        assert registry.get_latest_version() == "v1.1"


class TestPersistence:
    """Test registry persistence to disk."""

    def test_registry_saved_to_disk(self, temp_registry):
        """Registry persisted to JSON file."""
        registry, registry_path = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )

        # Verify file exists and has correct content
        assert registry_path.exists()
        with open(registry_path) as f:
            data = json.load(f)
        assert "v1.0" in data
        assert data["v1.0"]["accuracy"] == 0.85

    def test_registry_loaded_from_disk(self, temp_registry):
        """Registry loaded from persisted JSON file."""
        registry, registry_path = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )

        # Create new registry from same file
        registry2 = ModelRegistry(path=str(registry_path))
        assert registry2.get_latest_version() == "v1.0"
        assert registry2.get_active_version() == "v1.0"


class TestSupersededBy:
    """Test version history tracking via superseded_by."""

    def test_register_model_sets_superseded_by(self, temp_registry):
        """New registration marks old version as superseded."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            samples_used=100,
            auto_increment=False,
        )
        registry.register_model(
            version="v1.1",
            accuracy=0.90,
            samples_used=150,
            auto_increment=False,
        )

        v1_info = registry.get_model_info("v1.0")
        assert v1_info["superseded_by"] == "v1.1"
        assert v1_info["status"] == "inactive"


class TestModelMetadata:
    """Test model metadata tracking."""

    def test_register_stores_metadata(self, temp_registry):
        """Model registration stores accuracy, samples, and timestamp."""
        registry, _ = temp_registry
        registry.register_model(
            version="v1.0",
            accuracy=0.85,
            precision={"class_a": 0.90, "class_b": 0.80},
            recall={"class_a": 0.85, "class_b": 0.82},
            samples_used=100,
            auto_increment=False,
        )

        info = registry.get_model_info("v1.0")
        assert info["accuracy"] == 0.85
        assert info["samples_used"] == 100
        assert "trained_at" in info
        assert isinstance(info["trained_at"], str)

    def test_get_model_info_defaults_to_active(self, temp_registry):
        """get_model_info() without version returns active."""
        registry, _ = temp_registry
        registry.register_model(version="v1.0", accuracy=0.85, samples_used=100, auto_increment=False)

        info = registry.get_model_info()  # No version specified
        assert info["accuracy"] == 0.85
        assert info["version"] == "v1.0"


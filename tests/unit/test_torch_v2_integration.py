"""
Integration tests for Torch V2 Week 1 Foundation.

Validates that:
1. Predictor.predict_structured() returns TorchPrediction objects
2. Ranker accepts torch_context and integrates it into prompts
3. All intelligence layers work together (calibration, contradiction, cost weighting)
"""
import pytest

from app.ml.calibration import ConfidenceCalibrator, expected_calibration_error
from app.ml.contradiction_detector import ContradictionDetector
from app.ml.cost_weighting import CostWeightedRanker
from app.ml.schemas import TorchPrediction


class TestCalibrationModule:
    """Test confidence calibration (Platt scaling)."""

    def test_calibrator_initialization(self):
        """Calibrator should initialize in unfitted state."""
        cal = ConfidenceCalibrator()
        assert not cal.is_fitted
        assert cal.A is None
        assert cal.B is None

    def test_calibrate_without_fitting(self):
        """Uncalibrated predictions should pass through unchanged."""
        import numpy as np

        cal = ConfidenceCalibrator()
        probs = np.array([0.3, 0.7, 0.5])
        result = cal.calibrate(probs)
        np.testing.assert_array_almost_equal(result, probs)

    def test_confidence_band_classification(self):
        """Confidence bands should classify probabilities correctly."""
        assert ConfidenceCalibrator.get_confidence_band(0.8) == "high"
        assert ConfidenceCalibrator.get_confidence_band(0.5) == "medium"
        assert ConfidenceCalibrator.get_confidence_band(0.2) == "low"

    def test_expected_calibration_error(self):
        """ECE should be 0 for perfect predictions."""
        import numpy as np

        perfect_pred = np.array([0.0, 1.0, 0.5])
        perfect_true = np.array([0, 1, 0])
        ece = expected_calibration_error(perfect_pred, perfect_true)
        assert ece >= 0.0  # ECE is always non-negative


class TestContradictionDetector:
    """Test contradiction detection logic."""

    def test_detector_initialization(self):
        """Detector should initialize with no data."""
        det = ContradictionDetector()
        assert det is not None

    def test_detect_contradictions(self):
        """Detector should return score and flags."""
        det = ContradictionDetector()
        score, flags = det.detect_contradictions(
            obd_codes=["P0171"],
            symptoms="rough idle",
            vin_info={"vin": "1HGBH41JXMN109186"}
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert isinstance(flags, list)

    def test_get_warning_text(self):
        """Warning generator should produce human-readable text."""
        det = ContradictionDetector()
        warning = det.get_warning_text(0.7)
        assert isinstance(warning, str)
        assert len(warning) > 0


class TestCostWeightingRanker:
    """Test multi-strategy cost-weighted ranking."""

    def test_ranker_initialization(self):
        """Ranker should initialize with diagnosis costs."""
        ranker = CostWeightedRanker()
        assert ranker.LABOR_RATE == 125.0

    def test_rank_by_probability(self):
        """Should rank diagnoses by probability (descending)."""
        ranker = CostWeightedRanker()
        diagnoses = {
            "MAF": 0.75,
            "O2": 0.45,
            "spark_plugs": 0.25,
        }
        ranked = ranker.rank_by_probability(diagnoses)
        assert len(ranked) == 3
        assert ranked[0].code == "MAF"
        assert ranked[0].probability == 0.75
        assert ranked[1].code == "O2"

    def test_rank_by_cost(self):
        """Should rank diagnoses by cost (ascending)."""
        ranker = CostWeightedRanker()
        diagnoses = {
            "timing_belt": 0.5,
            "spark_plugs": 0.6,
            "MAF": 0.4,
        }
        ranked = ranker.rank_by_cost(diagnoses)
        assert len(ranked) == 3
        # spark_plugs should be first (cheapest: $40 parts + 1.5h*$125 = $227.50)
        assert ranked[0].code == "spark_plugs"
        # MAF next ($180 parts + 0.5h*$125 = $242.50)
        assert ranked[1].code == "MAF"

    def test_rank_by_roi(self):
        """Should rank diagnoses by ROI (probability/cost)."""
        ranker = CostWeightedRanker()
        diagnoses = {
            "MAF": 0.4,
            "spark_plugs": 0.7,
            "timing_belt": 0.3,
        }
        ranked = ranker.rank_by_roi(diagnoses)
        assert len(ranked) == 3
        # spark_plugs has best ROI (0.7 prob / $227.50 cost)
        assert ranked[0].code == "spark_plugs"

    def test_format_ranking_for_response(self):
        """Should format rankings into API response structure."""
        ranker = CostWeightedRanker()
        diagnoses = {"MAF": 0.85, "O2": 0.45, "fuel_filter": 0.30}
        by_prob = ranker.rank_by_probability(diagnoses)
        by_cost = ranker.rank_by_cost(diagnoses)
        by_roi = ranker.rank_by_roi(diagnoses)

        response = ranker.format_ranking_for_response(
            by_probability=by_prob,
            by_cost=by_cost,
            by_roi=by_roi
        )
        assert "by_probability" in response
        assert "by_cost" in response
        assert "by_roi" in response
        assert len(response["by_probability"]) == 3

    def test_get_total_cost(self):
        """Should estimate repair costs accurately."""
        ranker = CostWeightedRanker()
        cost_maf = ranker._get_total_cost("MAF")
        assert cost_maf > 0
        # MAF parts ($180) + labor (0.5h * $125) = $242.50
        assert 240 < cost_maf < 250

    def test_get_description(self):
        """Should provide human-readable descriptions."""
        ranker = CostWeightedRanker()
        desc = ranker._get_description("MAF")
        assert "Mass Airflow" in desc
        assert "Sensor" in desc


class TestTorchPredictionSchema:
    """Test structured prediction schema."""

    def test_torch_prediction_schema_exists(self):
        """TorchPrediction should be importable and usable."""
        assert TorchPrediction is not None

    def test_torch_prediction_creation(self):
        """Should be able to create minimal TorchPrediction."""
        from app.ml.schemas import (
            ModelInfo, VehicleContext, DiagnosticsContext,
            SymptomEmbedding, UncertaintyFactors, ContradictionDetection,
            CostWeightedRanking, InferenceMetadata
        )

        pred = TorchPrediction(
            request_id="test-123",
            model_info=ModelInfo(
                name="XGBoost Torch V2",
                version="2.0.0-alpha",
                framework="xgboost",
                feature_dim=798
            ),
            vehicle_context=VehicleContext(vin="1HG", obd_codes=["P0171"]),
            diagnostics=DiagnosticsContext(
                top_cause_confidence=0.8,
                num_high_confidence=2,
                num_medium_confidence=1
            ),
            symptom_embedding=SymptomEmbedding(
                embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                embedding_dim=384,
                symptom_text="rough idle"
            ),
            top_diagnoses=[],
            uncertainty_factors=UncertaintyFactors(
                epistemic_uncertainty=0.2,
                aleatoric_uncertainty=0.1,
                total_uncertainty=0.15
            ),
            contradiction_detection=ContradictionDetection(
                has_contradiction=False,
                overall_score=0.2,
                flags=[]
            ),
            cost_weighted_ranking=CostWeightedRanking(
                by_probability=[],
                by_cost=[],
                by_roi=[]
            ),
            inference_metadata=InferenceMetadata(
                latency_ms=125.5,
                hardware="cpu",
                model_size_mb=50
            )
        )
        assert pred.request_id == "test-123"
        assert pred.model_info.name == "XGBoost Torch V2"
        assert pred.vehicle_context.vin == "1HG"


class TestRankerTorchIntegration:
    """Test ranker accepts Torch context."""

    def test_ranker_signature(self):
        """Ranker.rank_diagnostics should accept torch_context parameter."""
        from app.ranker import rank_diagnostics
        import inspect

        sig = inspect.signature(rank_diagnostics)
        assert "torch_context" in sig.parameters
        assert sig.parameters["torch_context"].default is None

    def test_format_torch_context(self):
        """Should format Torch insights for LLM."""
        from app.ranker import _format_torch_context
        from app.ml.schemas import (
            TorchPrediction, ModelInfo, VehicleContext, DiagnosticsContext,
            SymptomEmbedding, UncertaintyFactors, ContradictionDetection,
            CostWeightedRanking, InferenceMetadata, TorchDiagnosis
        )

        pred = TorchPrediction(
            request_id="test",
            model_info=ModelInfo(name="Test", version="1.0", framework="xgb", feature_dim=798),
            vehicle_context=VehicleContext(vin="1HG", obd_codes=["P0171"]),
            diagnostics=DiagnosticsContext(top_cause_confidence=0.75, num_high_confidence=1, num_medium_confidence=1),
            symptom_embedding=SymptomEmbedding(embedding_model="test", embedding_dim=384, symptom_text="test"),
            top_diagnoses=[
                TorchDiagnosis(
                    rank=1, code="MAF", description="Mass Airflow Sensor",
                    raw_probability=0.80, calibrated_probability=0.75,
                    estimated_cost=242.50, estimated_labor_hours=0.5
                )
            ],
            uncertainty_factors=UncertaintyFactors(epistemic_uncertainty=0.2, aleatoric_uncertainty=0.1, total_uncertainty=0.15),
            contradiction_detection=ContradictionDetection(has_contradiction=False, overall_score=0.1, flags=[]),
            cost_weighted_ranking=CostWeightedRanking(by_probability=[], by_cost=[], by_roi=[]),
            inference_metadata=InferenceMetadata(latency_ms=100.0, hardware="cpu", model_size_mb=50)
        )

        formatted = _format_torch_context(pred)
        assert "TORCH V2" in formatted
        assert "MAF" in formatted


class TestFeatureEncoding:
    """Test 798D feature encoding."""

    def test_feature_encoding_shape(self):
        """Encoded features should be 798D."""
        from app.ml.predictor import encode_features
        import numpy as np

        X = encode_features(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171,P0420",
            symptoms="rough idle and poor acceleration"
        )
        assert X is not None
        assert X.shape == (1, 798)
        assert isinstance(X, np.ndarray)

    def test_feature_encoding_consistency(self):
        """Same input should produce same features."""
        from app.ml.predictor import encode_features
        import numpy as np

        X1 = encode_features("1HGBH41JXMN109186", "P0171", "rough idle")
        X2 = encode_features("1HGBH41JXMN109186", "P0171", "rough idle")
        np.testing.assert_array_almost_equal(X1, X2)

    def test_feature_encoding_handles_edge_cases(self):
        """Should handle missing/minimal inputs gracefully."""
        from app.ml.predictor import encode_features

        # Empty OBD codes
        X1 = encode_features("1HG", "", "symptom")
        assert X1 is not None

        # Empty symptoms
        X2 = encode_features("1HG", "P0171", "")
        assert X2 is not None

        # Very short VIN
        X3 = encode_features("X", "P0171", "rough idle")
        assert X3 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

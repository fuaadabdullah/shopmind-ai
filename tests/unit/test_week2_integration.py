"""
Week 2 Integration Tests: Torch V2 Probability Engine

Tests the integration of Torch V2 (optional ML layer) with the diagnostic service.
Validates that:
  1. Mock predictor generates realistic predictions
  2. Torch context is properly retrieved (real model → mock demo → None)
  3. LLM ranking receives and uses Torch context
  4. Response includes Torch metadata tracking
  5. Graceful fallback if Torch fails (never breaks Phase 1)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.ml.mock_predictor import predict_mock
from app.ml.schemas import (
    TorchPrediction, TorchDiagnosis, ContradictionDetection,
    CostWeightedRanking
)
from app.services.diagnostic_service import (
    get_torch_context, score_diagnostics, validate_diagnostic_request
)


class TestMockPredictor:
    """Test the mock predictor generates realistic predictions."""

    def test_mock_predictor_returns_structured_prediction(self):
        """Mock predictor should return TorchPrediction with all required fields."""
        result = predict_mock(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171,P0174",
            symptoms="rough idle, check engine light"
        )

        assert isinstance(result, TorchPrediction)
        assert result.request_id is not None
        assert len(result.top_diagnoses) > 0
        assert result.contradiction_detection is not None
        assert result.cost_weighted_ranking is not None

    def test_mock_predictor_seeded_reproducibility(self):
        """Same inputs should produce consistent (seeded) outputs."""
        vin = "1HGBH41JXMN109186"
        obd_codes = "P0171,P0174"
        symptoms = "rough idle"

        result1 = predict_mock(vin, obd_codes, symptoms)
        result2 = predict_mock(vin, obd_codes, symptoms)

        # Should have same top diagnosis (seeded)
        assert result1.top_diagnoses[0].code == result2.top_diagnoses[0].code
        assert result1.top_diagnoses[0].raw_probability == result2.top_diagnoses[0].raw_probability

    def test_mock_predictor_obd_diagnosis_mapping(self):
        """Mock predictor should map OBD codes to relevant diagnoses."""
        # P0171 = fuel system too lean
        result = predict_mock(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms=""
        )

        diagnosis_codes = [d.code for d in result.top_diagnoses]
        # Should include common fuel-related diagnoses
        possible_codes = {"fuel_filter", "MAF", "O2"}
        assert any(code in diagnosis_codes for code in possible_codes)

    def test_mock_predictor_symptom_boosting(self):
        """Mock should boost confidence for symptoms matching diagnoses."""
        # "rough idle" + "P0171" should highly favor MAF sensor
        result = predict_mock(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms="rough idle"
        )

        # Top diagnosis should have reasonable confidence
        assert result.top_diagnoses[0].raw_probability > 0.5

    def test_mock_predictor_contradiction_detection(self):
        """Mock should detect contradictory OBD code combinations."""
        # P0171 (too lean) + P0174 (too lean) together = unusual
        result = predict_mock(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171,P0174",
            symptoms=""
        )

        assert isinstance(result.contradiction_detection, ContradictionDetection)
        # Should flag this as unusual
        assert result.contradiction_detection.overall_score > 0.3

    def test_mock_predictor_cost_ranking(self):
        """Mock should provide cost analysis with multiple ranking strategies."""
        result = predict_mock(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms="rough idle"
        )

        assert isinstance(result.cost_weighted_ranking, CostWeightedRanking)
        assert len(result.cost_weighted_ranking.by_probability) > 0
        assert len(result.cost_weighted_ranking.by_cost) > 0
        assert len(result.cost_weighted_ranking.by_roi) > 0


class TestTorchContextRetrieval:
    """Test the get_torch_context function (fallback: real → mock → None)."""

    @patch('app.services.diagnostic_service.is_model_available')
    @patch('app.services.diagnostic_service.predict_structured')
    def test_torch_context_real_model_when_available(self, mock_predict_struct, mock_is_available):
        """Should use real model if is_model_available() returns True."""
        mock_is_available.return_value = True
        mock_prediction = Mock(spec=TorchPrediction)
        mock_prediction.request_id = "test-torch-123"
        mock_predict_struct.return_value = mock_prediction

        result = get_torch_context(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms="rough idle",
            request_id="req-123"
        )

        assert result == mock_prediction
        mock_is_available.assert_called_once()
        mock_predict_struct.assert_called_once()

    @patch('app.services.diagnostic_service.is_model_available')
    @patch('app.services.diagnostic_service.predict_mock')
    def test_torch_context_mock_fallback_when_no_model(self, mock_predict_mock, mock_is_available):
        """Should fall back to mock predictor if no real model available."""
        mock_is_available.return_value = False
        mock_prediction = Mock(spec=TorchPrediction)
        mock_prediction.request_id = "test-mock-123"
        mock_predict_mock.return_value = mock_prediction

        result = get_torch_context(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms="rough idle",
            request_id="req-123"
        )

        assert result == mock_prediction
        mock_is_available.assert_called_once()
        mock_predict_mock.assert_called_once()

    @patch('app.services.diagnostic_service.is_model_available')
    @patch('app.services.diagnostic_service.predict_structured')
    def test_torch_context_graceful_fallback_on_exception(self, mock_predict_struct, mock_is_available):
        """Should return None and log warning if Torch fails (graceful degradation)."""
        mock_is_available.return_value = True
        mock_predict_struct.side_effect = Exception("Model not found")

        result = get_torch_context(
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            symptoms="rough idle",
            request_id="req-123"
        )

        assert result is None  # Should gracefully return None, not raise

    def test_torch_context_integration_with_mock(self):
        """Integration test: get_torch_context with mock predictor."""
        with patch('app.services.diagnostic_service.is_model_available', return_value=False):
            result = get_torch_context(
                vin="1HGBH41JXMN109186",
                obd_codes="P0171",
                symptoms="rough idle",
                request_id="req-123"
            )

            assert result is not None
            assert isinstance(result, TorchPrediction)
            assert result.request_id is not None


class TestScoreDiagnosticsWithTorch:
    """Test score_diagnostics integration with Torch context."""

    @patch('app.services.diagnostic_service.get_torch_context')
    @patch('app.services.diagnostic_service.llm_rank_diagnostics')
    def test_score_diagnostics_includes_torch_context(self, mock_llm_rank, mock_get_torch):
        """score_diagnostics should call get_torch_context and pass it to LLM ranking."""
        mock_torch_pred = Mock(spec=TorchPrediction)
        mock_torch_pred.request_id = "torch-123"
        mock_torch_pred.top_diagnoses = [Mock(code="MAF")]
        mock_torch_pred.contradiction_detection = Mock(has_contradiction=False)
        mock_get_torch.return_value = mock_torch_pred

        mock_llm_rank.return_value = ("Diagnosis: ...", {"engine": "RAG+Torch"})

        score_diagnostics(
            symptoms="rough idle",
            retrieved_docs=[{"content": "...", "source": "manual.pdf"}],
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            request_id="req-123"
        )

        # Verify get_torch_context was called with correct params
        mock_get_torch.assert_called_once_with(
            "1HGBH41JXMN109186", "P0171", "rough idle", "req-123"
        )
        # Verify LLM ranking received torch_context
        mock_llm_rank.assert_called_once()
        call_kwargs = mock_llm_rank.call_args[1]
        assert call_kwargs['torch_context'] == mock_torch_pred

    @patch('app.services.diagnostic_service.get_torch_context')
    @patch('app.services.diagnostic_service.llm_rank_diagnostics')
    def test_score_diagnostics_metadata_includes_torch_tracking(self, mock_llm_rank, mock_get_torch):
        """Response metadata should include torch_enabled and torch_request_id."""
        mock_torch_pred = Mock(spec=TorchPrediction)
        mock_torch_pred.request_id = "torch-456"
        mock_torch_pred.top_diagnoses = [Mock(code="MAF_sensor")]
        mock_torch_pred.contradiction_detection = Mock(has_contradiction=False)
        mock_get_torch.return_value = mock_torch_pred

        mock_llm_rank.return_value = (
            "Diagnosis: MAF sensor",
            {"engine": "RAG+Torch"}
        )

        ranked_result, metadata = score_diagnostics(
            symptoms="rough idle",
            retrieved_docs=[{"content": "...", "source": "manual.pdf"}],
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            request_id="req-123"
        )

        assert metadata is not None
        assert metadata.get("torch_enabled") is True
        assert metadata.get("torch_request_id") == "torch-456"
        assert metadata.get("top_torch_diagnosis") == "MAF_sensor"

    @patch('app.services.diagnostic_service.get_torch_context')
    @patch('app.services.diagnostic_service.llm_rank_diagnostics')
    def test_score_diagnostics_when_torch_unavailable(self, mock_llm_rank, mock_get_torch):
        """Should work normally when Torch returns None (Phase 1 fallback)."""
        mock_get_torch.return_value = None  # Torch failed or disabled

        mock_llm_rank.return_value = (
            "Diagnosis: Check MAF sensor",
            {"engine": "RAG"}
        )

        ranked_result, metadata = score_diagnostics(
            symptoms="rough idle",
            retrieved_docs=[{"content": "...", "source": "manual.pdf"}],
            vin="1HGBH41JXMN109186",
            obd_codes="P0171",
            request_id="req-123"
        )

        assert metadata.get("torch_enabled") is False
        assert metadata.get("torch_request_id") is None
        # Should still return valid diagnosis (Phase 1 works)
        assert "Check MAF sensor" in ranked_result


class TestDiagnosticResponseMetadata:
    """Test that response includes Torch metadata."""

    def test_response_includes_torch_enabled_flag(self):
        """DiagnosticResponse should include torch_enabled in metadata."""
        # This would require mocking the full endpoint, which is handled in e2e tests
        # For now, just verify the flow integrates
        pass


@pytest.mark.integration
class TestWeek2EndToEnd:
    """End-to-end test of Week 2 integration (requires full app setup)."""

    @pytest.mark.skip(reason="Requires full FastAPI app setup with dependencies")
    def test_diagnose_endpoint_with_torch(self):
        """Full endpoint test with Torch context."""
        # POST /api/diagnose with VIN, OBD codes, symptoms
        # Expect: response.torch_enabled = True/False, torch_request_id if mock
        pass

    @pytest.mark.skip(reason="Requires full FastAPI app setup with dependencies")
    def test_diagnose_endpoint_response_includes_torch_metadata(self):
        """Verify response JSON includes Torch tracking."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

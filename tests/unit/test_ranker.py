import pytest
from unittest.mock import patch, MagicMock

from app.ranker import rank_diagnostics


class TestRankDiagnostics:
    """Unit tests for the rank_diagnostics function (Phase 1: Pure RAG)."""

    @pytest.mark.unit
    def test_rank_diagnostics_returns_tuple(self, mock_provider):
        """Test that rank_diagnostics returns a tuple (text, metadata)."""
        mock_provider.generate.return_value = "Test ranking"
        result = rank_diagnostics("car won't start", [{"content": "test", "source": "Manual"}])
        assert isinstance(result, tuple)
        assert len(result) == 2
        ranking_text, metadata = result
        assert isinstance(ranking_text, str)
        assert isinstance(metadata, dict)

    @pytest.mark.unit
    def test_rank_diagnostics_metadata_structure(self, mock_provider):
        """Test that metadata includes expected fields."""
        mock_provider.generate.return_value = "Test ranking"
        _, metadata = rank_diagnostics(
            "symptoms",
            [{"content": "content", "source": "Manual-001"}]
        )
        assert "engine" in metadata
        assert "num_docs" in metadata
        assert "doc_sources" in metadata
        assert "phase" in metadata
        assert metadata["engine"] == "RAG + optional Torch V2"
        assert metadata["phase"] == "Phase 1 (RAG) + optional Phase 2 (Torch probability)"

    @pytest.mark.unit
    def test_rank_diagnostics_calls_provider(self, mock_provider):
        """Test that rank_diagnostics calls the provider."""
        mock_provider.generate.return_value = "Result"
        symptoms = "car won't start"
        retrieved_docs = [{"content": "Battery test", "source": "TSB-001"}]
        rank_diagnostics(symptoms, retrieved_docs)
        mock_provider.generate.assert_called_once()

    @pytest.mark.unit
    def test_rank_diagnostics_prompt_includes_symptoms(self, mock_provider):
        """Test that the prompt includes symptoms."""
        mock_provider.generate.return_value = "Result"
        symptoms = "car won't start, clicking sound"
        retrieved_docs = [{"content": "test", "source": "Manual"}]
        rank_diagnostics(symptoms, retrieved_docs)
        
        call_args = mock_provider.generate.call_args[0][0]
        assert symptoms in call_args

    @pytest.mark.unit
    def test_rank_diagnostics_prompt_includes_doc_sources(self, mock_provider):
        """Test that the prompt includes doc sources."""
        mock_provider.generate.return_value = "Result"
        symptoms = "car won't start"
        retrieved_docs = [
            {"content": "Battery content", "source": "TSB-Battery-001"},
            {"content": "Starter content", "source": "Manual-Starter"}
        ]
        rank_diagnostics(symptoms, retrieved_docs)
        
        call_args = mock_provider.generate.call_args[0][0]
        assert "[Source 1:" in call_args
        assert "[Source 2:" in call_args
        assert "TSB-Battery-001" in call_args
        assert "Manual-Starter" in call_args

    @pytest.mark.unit
    def test_rank_diagnostics_empty_symptoms_error(self):
        """Test rank_diagnostics returns error dict for empty symptoms."""
        result = rank_diagnostics("", [{"content": "test", "source": "Manual"}])
        assert isinstance(result, tuple)
        assert result[0] == "Error: No symptoms provided"
        assert result[1] == {}

    @pytest.mark.unit
    def test_rank_diagnostics_empty_docs_error(self):
        """Test rank_diagnostics returns error for empty retrieved docs."""
        result = rank_diagnostics("symptoms", [])
        assert isinstance(result, tuple)
        assert result[0] == "Error: No relevant diagnostic information found"
        assert result[1] == {}

    @pytest.mark.unit
    def test_rank_diagnostics_with_vin_obd(self, mock_provider):
        """Test rank_diagnostics includes VIN and OBD codes in prompt."""
        mock_provider.generate.return_value = "Result"
        symptoms = "Check engine light"
        retrieved_docs = [{"content": "test", "source": "Manual"}]
        vin = "1HG123456"
        obd_codes = "P0420,P0171"
        
        rank_diagnostics(symptoms, retrieved_docs, vin=vin, obd_codes=obd_codes)
        
        call_args = mock_provider.generate.call_args[0][0]
        assert vin in call_args
        assert obd_codes in call_args

    @pytest.mark.unit
    @patch('app.ranker.get_provider')
    def test_rank_diagnostics_handles_provider_error(self, mock_get_provider):
        """Test that rank_diagnostics raises RankingError on provider failure."""
        from app.exceptions import RankingError
        
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = Exception("Provider unavailable")
        mock_get_provider.return_value = mock_provider
        
        with pytest.raises(RankingError):
            rank_diagnostics("symptoms", [{"content": "test", "source": "Manual"}])

    @pytest.mark.unit
    def test_rank_diagnostics_multiple_docs_increases_num_docs(self, mock_provider):
        """Test that metadata correctly counts documents."""
        mock_provider.generate.return_value = "Result"
        retrieved_docs = [
            {"content": f"Doc {i}", "source": f"Manual-{i:03d}"}
            for i in range(5)
        ]
        _, metadata = rank_diagnostics("symptoms", retrieved_docs)
        
        assert metadata["num_docs"] == 5

    @pytest.mark.unit
    def test_rank_diagnostics_unique_sources(self, mock_provider):
        """Test that metadata lists unique doc sources."""
        mock_provider.generate.return_value = "Result"
        retrieved_docs = [
            {"content": "Doc 1", "source": "Manual-A"},
            {"content": "Doc 2", "source": "Manual-A"},  # Duplicate source
            {"content": "Doc 3", "source": "Manual-B"},
        ]
        _, metadata = rank_diagnostics("symptoms", retrieved_docs)
        
        sources = metadata["doc_sources"]
        assert len(sources) == 2
        assert "Manual-A" in sources
        assert "Manual-B" in sources

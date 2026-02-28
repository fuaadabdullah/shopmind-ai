"""
Integration tests for LLM fallback chain and degraded mode.

Tests cover:
- Primary provider failure triggers fallback
- Fallback provider success is recorded
- Both providers failing triggers degraded mode
- Degraded mode returns FAISS results
- Metadata flags track LLM availability and fallback usage
"""
from unittest.mock import Mock, patch

from app.exceptions import ProviderError
from app.ranker import (
    _call_llm_with_fallback,
    _format_degraded_mode_results,
    rank_diagnostics,
)


class TestCallLLMWithFallback:
    """Test the fallback chain when primary provider fails."""

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_primary_provider_success_no_fallback(self, mock_get_fallback, mock_get_provider):
        """When primary provider succeeds, no fallback is attempted."""
        # Setup primary provider to succeed
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(return_value="Primary response")
        mock_get_provider.return_value = mock_primary

        # Fallback should not be called
        mock_get_fallback.return_value = None

        result, provider_name, used_fallback = _call_llm_with_fallback("test prompt")

        assert result == "Primary response"
        assert provider_name == "gcp"
        assert used_fallback is False
        mock_get_fallback.assert_not_called()

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_primary_circuit_breaker_triggers_fallback(self, mock_get_fallback, mock_get_provider):
        """When primary circuit breaker opens, fallback is attempted."""
        # Setup primary provider to fail with circuit breaker error
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Circuit breaker open - too many failures")
        )
        mock_get_provider.return_value = mock_primary

        # Setup fallback provider to succeed
        mock_fallback = Mock()
        mock_fallback.provider_name = "siliconeflow"
        mock_fallback.generate = Mock(return_value="Fallback response")
        mock_get_fallback.return_value = mock_fallback

        result, provider_name, used_fallback = _call_llm_with_fallback("test prompt")

        assert result == "Fallback response"
        assert provider_name == "gcp"  # Still reports primary provider name
        assert used_fallback is True
        mock_get_fallback.assert_called_once()

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_both_providers_fail_returns_none(self, mock_get_fallback, mock_get_provider):
        """When both providers fail, returns None for degraded mode."""
        # Setup primary provider to fail
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Circuit breaker open")
        )
        mock_get_provider.return_value = mock_primary

        # Setup fallback provider to also fail
        mock_fallback = Mock()
        mock_fallback.provider_name = "siliconeflow"
        mock_fallback.generate = Mock(
            side_effect=ProviderError("Fallback also failed")
        )
        mock_get_fallback.return_value = mock_fallback

        result, provider_name, used_fallback = _call_llm_with_fallback("test prompt")

        assert result is None
        assert provider_name == "gcp"
        assert used_fallback is True  # Fallback was attempted (even though it failed)

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_no_fallback_provider_configured(self, mock_get_fallback, mock_get_provider):
        """When primary fails and no fallback configured, returns None."""
        # Setup primary provider to fail
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Circuit breaker open")
        )
        mock_get_provider.return_value = mock_primary

        # No fallback provider configured
        mock_get_fallback.return_value = None

        result, provider_name, used_fallback = _call_llm_with_fallback("test prompt")

        assert result is None
        assert provider_name == "gcp"
        assert used_fallback is False  # Didn't use fallback since none available

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_non_circuit_breaker_error_not_fallback(self, mock_get_fallback, mock_get_provider):
        """Non-circuit-breaker errors should not trigger fallback."""
        # Setup primary provider to fail with non-CB error
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Authentication failed")
        )
        mock_get_provider.return_value = mock_primary

        mock_get_fallback.return_value = None

        # Should re-raise, not fallback
        try:
            _call_llm_with_fallback("test prompt")
            raise AssertionError("Expected ProviderError to be raised")
        except ProviderError as e:
            assert "Authentication failed" in str(e)

        mock_get_fallback.assert_not_called()


class TestDegradedModeResponse:
    """Test degraded mode formatting when LLM is unavailable."""

    def test_degraded_mode_with_docs(self):
        """Degraded mode should format FAISS docs with relevance scores."""
        docs = [
            {
                "content": "MAF sensor cleaning procedure",
                "source": "TSB-001",
                "relevance_score": 0.95
            },
            {
                "content": "Air intake system inspection",
                "source": "Manual-Ch3",
                "relevance_score": 0.87
            }
        ]

        result = _format_degraded_mode_results(docs)

        # Should include degraded mode message
        assert "DEGRADED MODE" in result
        assert "temporarily unavailable" in result

        # Should include doc sources and relevance
        assert "TSB-001" in result
        assert "Manual-Ch3" in result
        assert "95.00%" in result or "95%" in result or "0.95" in result
        assert "87.00%" in result or "87%" in result or "0.87" in result

    def test_degraded_mode_no_docs(self):
        """Degraded mode without docs should show user-friendly message."""
        result = _format_degraded_mode_results([])

        assert "Connection to diagnostic reasoning service" in result
        assert "temporarily unavailable" in result
        assert "try again later" in result

    def test_degraded_mode_truncates_long_content(self):
        """Degraded mode should truncate very long document content."""
        docs = [
            {
                "content": "A" * 500,  # Very long content
                "source": "TSB-001",
                "relevance_score": 0.95
            }
        ]

        result = _format_degraded_mode_results(docs)

        # Should truncate content
        assert "A" * 400 not in result  # Shouldn't have 400+ A's


class TestRankDiagnosticsWithFallback:
    """Test rank_diagnostics integration with fallback and degraded mode."""

    @patch('app.ranker._call_llm_with_fallback')
    def test_rank_diagnostics_normal_mode(self, mock_call_llm):
        """rank_diagnostics should work normally when LLM available."""
        mock_call_llm.return_value = (
            "1. MAF Sensor: ...\n2. EGR Valve: ...",
            "gcp",
            False
        )

        result, metadata = rank_diagnostics(
            symptoms="Check engine light",
            retrieved_docs=[
                {"content": "MAF sensor info", "source": "Manual"},
                {"content": "EGR valve info", "source": "Manual"}
            ]
        )

        assert "MAF Sensor" in result
        assert metadata["llm_unavailable"] is False
        assert metadata["fallback_used"] is False

    @patch('app.ranker._call_llm_with_fallback')
    def test_rank_diagnostics_degraded_mode_when_llm_unavailable(self, mock_call_llm):
        """rank_diagnostics should degrade gracefully when LLM unavailable."""
        # Simulate both providers down
        mock_call_llm.return_value = (None, "gcp", True)

        result, metadata = rank_diagnostics(
            symptoms="Check engine light",
            retrieved_docs=[
                {"content": "MAF sensor info", "source": "Manual", "relevance_score": 0.95},
                {"content": "EGR valve info", "source": "Manual", "relevance_score": 0.87}
            ]
        )

        # Should return degraded mode response
        assert "DEGRADED MODE" in result or "Manual" in result
        assert metadata["llm_unavailable"] is True
        assert metadata["fallback_used"] is True

    @patch('app.ranker._call_llm_with_fallback')
    def test_rank_diagnostics_fallback_metadata(self, mock_call_llm):
        """rank_diagnostics should record when fallback was used."""
        mock_call_llm.return_value = (
            "Fallback provider response",
            "gcp",
            True  # Fallback was used
        )

        result, metadata = rank_diagnostics(
            symptoms="Check engine light",
            retrieved_docs=[
                {"content": "MAF sensor info", "source": "Manual"}
            ]
        )

        assert metadata["llm_unavailable"] is False  # LLM was available (fallback succeeded)
        assert metadata["fallback_used"] is True


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_full_primary_failure_to_degraded_chain(self, mock_get_fallback, mock_get_provider):
        """Test complete chain: primary fails → fallback fails → degraded mode."""
        # Setup primary to fail
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Circuit breaker open")
        )
        mock_get_provider.return_value = mock_primary

        # Setup fallback to fail
        mock_fallback = Mock()
        mock_fallback.provider_name = "siliconeflow"
        mock_fallback.generate = Mock(
            side_effect=ProviderError("Also failed")
        )
        mock_get_fallback.return_value = mock_fallback

        # Call rank_diagnostics
        _, metadata = rank_diagnostics(
            symptoms="Check engine light, rough idle",
            retrieved_docs=[
                {
                    "content": "MAF sensor cleaning: Remove sensor, blow out with air",
                    "source": "Manual-Ch5",
                    "relevance_score": 0.92
                }
            ]
        )

        # Should have degraded mode result
        assert metadata["llm_unavailable"] is True
        assert metadata["fallback_used"] is True

    @patch('app.ranker.get_provider')
    @patch('app.ranker.get_fallback_provider')
    def test_primary_failure_fallback_success_chain(self, mock_get_fallback, mock_get_provider):
        """Test chain: primary fails → fallback succeeds → normal response."""
        # Setup primary to fail
        mock_primary = Mock()
        mock_primary.provider_name = "gcp"
        mock_primary.generate = Mock(
            side_effect=ProviderError("Circuit breaker open")
        )
        mock_get_provider.return_value = mock_primary

        # Setup fallback to succeed
        mock_fallback = Mock()
        mock_fallback.provider_name = "siliconeflow"
        mock_fallback.generate = Mock(return_value="1. MAF Sensor\n2. EGR Valve")
        mock_get_fallback.return_value = mock_fallback

        # Call rank_diagnostics
        result, metadata = rank_diagnostics(
            symptoms="Check engine light",
            retrieved_docs=[
                {"content": "MAF sensor info", "source": "Manual"}
            ]
        )

        # Should have normal LLM response
        assert "MAF Sensor" in result
        assert metadata["llm_unavailable"] is False  # LLM (fallback) was available
        assert metadata["fallback_used"] is True  # Fallback was used

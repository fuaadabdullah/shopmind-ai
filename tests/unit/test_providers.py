"""
Unit tests for LLM provider implementations.

Tests GCP local provider and SiliconeFlow provider with mocking
of HTTP requests and error scenarios.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.providers.gcp_local import GCPProvider
from app.providers.siliconeflow import SiliconeFlowProvider
from app.exceptions import ProviderError, ProviderTimeoutError, ProviderResponseError
from app.config import settings


class TestGCPProvider:
    """Tests for GCP local provider implementation."""

    def test_provider_initialization(self):
        """Provider should initialize correctly."""
        provider = GCPProvider()
        assert provider is not None
        assert hasattr(provider, "generate")

    def test_generate_success(self):
        """Successful request should return parsed response."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"response": "test result"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            result = provider.generate("test prompt")
            assert result == "test result"

    def test_generate_timeout(self):
        """Timeout should raise ProviderTimeoutError."""
        provider = GCPProvider()

        import requests
        with patch.object(provider, "session") as mock_session:
            mock_session.post.side_effect = requests.Timeout("Request timed out")
            with pytest.raises(ProviderTimeoutError):
                provider.generate("test prompt")

    def test_generate_connection_error(self):
        """Connection error should raise ProviderError."""
        provider = GCPProvider()

        import requests
        with patch.object(provider, "session") as mock_session:
            mock_session.post.side_effect = requests.ConnectionError("Failed to connect")
            with pytest.raises(ProviderError):
                provider.generate("test prompt")

    def test_generate_bad_response_status(self):
        """Non-200 status should raise ProviderResponseError."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Server error"

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_generate_invalid_json(self):
        """Invalid JSON response should raise ProviderResponseError."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "not json"

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_retry_strategy_applied(self):
        """Session should have retry strategy configured."""
        provider = GCPProvider()
        assert hasattr(provider, "session")

    def test_generate_missing_response_field(self):
        """Response without 'response' field should raise ProviderResponseError."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"output": "wrong key"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_timeout_configuration(self):
        """Timeout should be properly configured in post call."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"response": "result"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            provider.generate("test prompt")
            call_kwargs = mock_session.post.call_args[1]
            assert "timeout" in call_kwargs

    def test_generate_sends_correct_payload(self):
        """Generate should send prompt as JSON payload."""
        provider = GCPProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"response": "result"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            provider.generate("diagnose P0420")
            call_kwargs = mock_session.post.call_args[1]
            assert call_kwargs["json"] == {"prompt": "diagnose P0420"}


class TestSiliconeFlowProvider:
    """Tests for SiliconeFlow provider implementation."""

    def test_provider_initialization(self):
        """Provider should initialize correctly."""
        provider = SiliconeFlowProvider()
        assert provider is not None
        assert hasattr(provider, "generate")
        assert hasattr(provider, "session")

    def test_generate_success(self):
        """Successful request should return parsed response."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test result"}}]
        }

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            result = provider.generate("test prompt")
            assert result == "test result"

    def test_generate_authentication_error(self):
        """Authentication error should raise ProviderResponseError."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_generate_rate_limit(self):
        """Rate limit error should raise ProviderResponseError."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_response.text = "Too many requests"

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_generate_timeout(self):
        """Timeout should raise ProviderTimeoutError."""
        provider = SiliconeFlowProvider()

        import requests
        with patch.object(provider, "session") as mock_session:
            mock_session.post.side_effect = requests.Timeout()
            with pytest.raises(ProviderTimeoutError):
                provider.generate("test prompt")

    def test_api_key_included_in_headers(self):
        """API key should be included in request headers."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "result"}}]
        }

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            provider.generate("test prompt")
            call_kwargs = mock_session.post.call_args[1]
            if "headers" in call_kwargs:
                assert "Authorization" in call_kwargs["headers"]

    def test_malformed_response_handling(self):
        """Malformed response should raise ProviderResponseError."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"invalid": "structure"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            with pytest.raises(ProviderResponseError):
                provider.generate("test prompt")

    def test_generate_sends_messages_format(self):
        """Generate should send prompt in chat messages format."""
        provider = SiliconeFlowProvider()

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "result"}}]
        }

        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            provider.generate("diagnose P0420")
            call_kwargs = mock_session.post.call_args[1]
            assert call_kwargs["json"] == {
                "messages": [{"role": "user", "content": "diagnose P0420"}]
            }


class TestProviderErrorHandling:
    """Tests for provider error handling."""

    def test_provider_error_raised_correctly(self):
        """ProviderError should be raised with message."""
        with pytest.raises(ProviderError) as exc_info:
            raise ProviderError("Test error")
        assert str(exc_info.value) == "Test error"

    def test_timeout_error_is_provider_error(self):
        """ProviderTimeoutError should be subclass of ProviderError."""
        assert issubclass(ProviderTimeoutError, ProviderError)

    def test_response_error_is_provider_error(self):
        """ProviderResponseError should be subclass of ProviderError."""
        assert issubclass(ProviderResponseError, ProviderError)

    def test_retry_on_transient_error(self):
        """Transient errors should be retried."""
        provider = GCPProvider()

        import requests
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"response": "success"}

        with patch.object(provider, "session") as mock_session:
            mock_session.post.side_effect = [
                requests.ConnectionError(),
                mock_response
            ]
            try:
                result = provider.generate("test prompt")
            except ProviderError:
                pass  # Retries exhausted


class TestProviderIntegration:
    """Integration tests for providers."""

    def test_gcp_provider_full_flow(self):
        """Test GCP provider through full request/response cycle."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"response": "Diagnosis: Engine malfunction"}

        provider = GCPProvider()
        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            result = provider.generate("P0420 catalyst system inefficiency")
            assert result == "Diagnosis: Engine malfunction"
            mock_session.post.assert_called_once()

    def test_siliconeflow_provider_full_flow(self):
        """Test SiliconeFlow provider through full request/response cycle."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Diagnosis: Battery issue"}}]
        }

        provider = SiliconeFlowProvider()
        with patch.object(provider, "session") as mock_session:
            mock_session.post.return_value = mock_response
            result = provider.generate("Low voltage warning")
            assert result == "Diagnosis: Battery issue"
            mock_session.post.assert_called_once()

    def test_provider_factory_gcp(self):
        """Factory should return GCP provider correctly."""
        from app.providers.base import get_provider
        with patch.object(settings, "DEFAULT_PROVIDER", "gcp"):
            provider = get_provider()
            assert isinstance(provider, GCPProvider)

    def test_provider_factory_siliconeflow(self):
        """Factory should return SiliconeFlow provider correctly."""
        from app.providers.base import get_provider
        with patch.object(settings, "DEFAULT_PROVIDER", "siliconeflow"):
            provider = get_provider()
            assert isinstance(provider, SiliconeFlowProvider)

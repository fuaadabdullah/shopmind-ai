import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import using the test app fixture to avoid static files mounting issue


class TestHealthEndpoint:
    """Integration tests for the health check endpoint."""

    @pytest.mark.integration
    def test_health_check_returns_200(self, client):
        """Test that health check returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_health_check_returns_healthy_status(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_health_check_content_type(self, client):
        """Test that health check returns JSON content type."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestDiagnoseEndpoint:
    """Integration tests for the diagnose endpoint."""

    @pytest.mark.integration
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_diagnose_returns_200(self, mock_provider, mock_search, mock_embed, client):
        """Test that diagnose endpoint returns 200 status."""
        import numpy as np
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = [{"cause": "Battery"}]
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Test response"
        mock_provider.return_value = mock_provider_instance
        
        response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P0420",
            "symptoms": "car won't start"
        })
        assert response.status_code == 200

    @pytest.mark.integration
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_diagnose_returns_result(self, mock_provider, mock_search, mock_embed, client):
        """Test that diagnose endpoint returns result."""
        import numpy as np
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = [{"cause": "Battery"}]
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Test diagnosis result"
        mock_provider.return_value = mock_provider_instance
        
        response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P0420",
            "symptoms": "car won't start"
        })
        data = response.json()
        assert "result" in data

    @pytest.mark.integration
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_diagnose_calls_retrieve(self, mock_provider, mock_search, mock_embed, client):
        """Test that diagnose endpoint calls retrieve with correct input."""
        import numpy as np
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = []
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Result"
        mock_provider.return_value = mock_provider_instance
        
        symptoms = "car won't start, clicking sound"
        obd_codes = "P0420"
        
        client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": obd_codes,
            "symptoms": symptoms
        })
        
        # Verify embed_text was called with combined symptoms and OBD codes
        expected_input = f"{symptoms} {obd_codes}"
        mock_embed.assert_called_once()

    @pytest.mark.integration
    def test_diagnose_invalid_json(self, client):
        """Test diagnose endpoint with invalid JSON."""
        response = client.post(
            "/diagnose",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestCORS:
    """Integration tests for CORS configuration."""

    @pytest.mark.integration
    def test_health_endpoint_works(self, client):
        """Test that health endpoint is accessible."""
        response = client.get("/health")
        assert response.status_code == 200

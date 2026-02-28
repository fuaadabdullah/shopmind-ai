import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from fastapi.testclient import TestClient


class TestCompleteDiagnosticWorkflow:
    """End-to-end tests for the complete diagnostic workflow."""

    @pytest.mark.e2e
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_full_diagnostic_workflow(self, mock_provider, mock_search, mock_embed, client):
        """Test the complete diagnostic workflow from request to response."""
        # Set up mocks for the entire workflow
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = [
            {"cause": "Battery Issues", "description": "Dead battery", "tests": ["voltage test"]},
            {"cause": "Starter Motor", "description": "Bad starter", "tests": ["starter test"]}
        ]
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Top diagnosis: Battery Issues"
        mock_provider.return_value = mock_provider_instance
        
        # Make the diagnostic request
        response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P0420",
            "symptoms": "car won't start, clicking sound"
        })
        
        # Verify the complete workflow
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert isinstance(data["result"], str)

    @pytest.mark.e2e
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_workflow_with_multiple_symptoms(self, mock_provider, mock_search, mock_embed, client):
        """Test workflow with multiple symptoms."""
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = [{"cause": "Multiple issues"}]
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Diagnosis result"
        mock_provider.return_value = mock_provider_instance
        
        response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P0300,P0420,P0128",
            "symptoms": "car won't start, engine stalling, overheating"
        })
        
        assert response.status_code == 200

    @pytest.mark.e2e
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_workflow_empty_retrieval_results(self, mock_provider, mock_search, mock_embed, client):
        """Test workflow when retrieval returns no results."""
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = []  # No results
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "No diagnosis possible"
        mock_provider.return_value = mock_provider_instance
        
        response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P9999",
            "symptoms": "unknown symptom xyz"
        })
        
        assert response.status_code == 200

    @pytest.mark.e2e
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_workflow_with_known_vin(self, mock_provider, mock_search, mock_embed, client):
        """Test workflow with a known VIN."""
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = [{"cause": "Known issue"}]
        
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "VIN-specific diagnosis"
        mock_provider.return_value = mock_provider_instance
        
        # Test with a sample VIN
        response = client.post("/diagnose", json={
            "vin": "JM1BK343551316012",  # Sample Mazda VIN
            "obdcodes": "P0171",
            "symptoms": "rough idle, check engine light"
        })
        
        assert response.status_code == 200

    @pytest.mark.e2e
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    @patch('app.ranker.get_provider')
    def test_health_check_workflow(self, mock_provider, mock_search, mock_embed, client):
        """Test that health check works alongside main workflow."""
        # First check health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"
        
        # Then run diagnostic
        mock_embed.return_value = np.random.rand(1, 384)
        mock_search.return_value = []
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate.return_value = "Test"
        mock_provider.return_value = mock_provider_instance
        
        diag_response = client.post("/diagnose", json={
            "vin": "1HGBH41JXMN109186",
            "obdcodes": "P0420",
            "symptoms": "test"
        })
        assert diag_response.status_code == 200

    @pytest.mark.e2e
    def test_api_documentation_accessible(self, client):
        """Test that API documentation is accessible."""
        # Try to access OpenAPI docs
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        # Try to access Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200


class TestErrorScenarios:
    """E2E tests for error scenarios and edge cases."""

    @pytest.mark.e2e
    def test_invalid_request_body(self, client):
        """Test handling of invalid request body."""
        response = client.post("/diagnose", json={
            "wrong_field": "value"
        })
        
        # Should return validation error
        assert response.status_code == 422

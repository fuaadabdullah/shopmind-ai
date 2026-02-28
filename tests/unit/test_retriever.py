import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.retriever import retrieve


class TestRetrieve:
    """Unit tests for the retrieve function."""

    @pytest.mark.unit
    def test_retrieve_returns_list(self, mock_embeddings, mock_vector_store):
        """Test that retrieve returns a list of results."""
        result = retrieve("car won't start")
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_retrieve_returns_top_k_results(self, mock_embeddings, mock_vector_store):
        """Test that retrieve returns the correct number of results."""
        result = retrieve("car won't start")
        assert len(result) == 2  # Based on mock return value

    @pytest.mark.unit
    def test_retrieve_calls_embed_text(self, mock_embeddings, mock_vector_store):
        """Test that retrieve calls embed_text with correct input."""
        symptoms = "car won't start, clicking sound"
        retrieve(symptoms)
        mock_embeddings.assert_called_once_with([symptoms])

    @pytest.mark.unit
    def test_retrieve_calls_search(self, mock_embeddings, mock_vector_store):
        """Test that retrieve calls search with the embedded vector."""
        retrieve("car won't start")
        mock_vector_store.assert_called_once()

    @pytest.mark.unit
    def test_retrieve_with_empty_symptoms(self, mock_embeddings, mock_vector_store):
        """Test retrieve with empty symptoms string returns empty list."""
        result = retrieve("")
        # Empty symptoms should short-circuit without calling embed_text
        mock_embeddings.assert_not_called()
        assert result == []

    @pytest.mark.unit
    def test_retrieve_with_long_symptoms(self, mock_embeddings, mock_vector_store):
        """Test retrieve with a very long symptoms string."""
        long_symptoms = " ".join(["symptom"] * 1000)
        result = retrieve(long_symptoms)
        mock_embeddings.assert_called_once()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_retrieve_result_format(self, mock_embeddings, mock_vector_store):
        """Test that retrieve returns correctly formatted results."""
        result = retrieve("car won't start")
        assert isinstance(result[0], dict)
        assert "cause" in result[0]
        assert "description" in result[0]

    @pytest.mark.unit
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    def test_retrieve_handles_embedding_error(self, mock_search, mock_embed):
        """Test that retrieve handles embedding errors gracefully."""
        mock_embed.side_effect = Exception("Embedding service unavailable")
        
        with pytest.raises(Exception):
            retrieve("car won't start")

    @pytest.mark.unit
    @patch('app.retriever.embed_text')
    @patch('app.retriever.search')
    def test_retrieve_handles_search_error(self, mock_search, mock_embed):
        """Test that retrieve handles search errors gracefully."""
        mock_embed.return_value = [np.random.rand(384).tolist()]
        mock_search.side_effect = Exception("Vector store unavailable")
        
        with pytest.raises(Exception):
            retrieve("car won't start")

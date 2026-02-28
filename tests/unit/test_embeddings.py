"""
Unit tests for the text embedding functionality.

Tests embed_text with mocked SentenceTransformer model
since sentence-transformers may not be installed.
"""
import pytest
from unittest.mock import patch, Mock
import numpy as np


class TestEmbedText:
    """Unit tests for the embed_text function."""

    @pytest.mark.unit
    def test_embed_text_returns_array(self):
        """Test that embed_text returns a numpy array."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)

        with patch('app.embeddings._get_model', return_value=mock_model):
            from app.embeddings import embed_text
            result = embed_text("test text")
            assert isinstance(result, np.ndarray)

    @pytest.mark.unit
    def test_embed_text_returns_correct_shape(self):
        """Test that embed_text returns correct shape for single input."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)

        with patch('app.embeddings._get_model', return_value=mock_model):
            from app.embeddings import embed_text
            result = embed_text("test text")
            assert result.shape[0] == 1
            assert result.shape[1] == 384

    @pytest.mark.unit
    def test_embed_text_calls_model(self):
        """Test that embed_text calls the model's encode method."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)

        with patch('app.embeddings._get_model', return_value=mock_model):
            from app.embeddings import embed_text
            embed_text("test text")
            mock_model.encode.assert_called()

    @pytest.mark.unit
    def test_embed_text_with_list_of_strings(self):
        """Test embed_text with a list of strings."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(3, 384).astype(np.float32)

        with patch('app.embeddings._get_model', return_value=mock_model):
            from app.embeddings import embed_text
            texts = ["text1", "text2", "text3"]
            result = embed_text(texts)
            assert result.shape[0] == 3

    @pytest.mark.unit
    def test_embed_text_handles_model_error(self):
        """Test that embed_text handles model errors gracefully."""
        from app.exceptions import EmbeddingError

        with patch('app.embeddings._get_model', side_effect=EmbeddingError("Model loading error")):
            from app.embeddings import embed_text
            with pytest.raises(EmbeddingError):
                embed_text("test text")

    @pytest.mark.unit
    def test_embed_text_embedding_dimension(self):
        """Test that embed_text returns embeddings of correct dimension."""
        mock_model = Mock()
        embedding_dim = 384
        mock_model.encode.return_value = np.random.rand(1, embedding_dim).astype(np.float32)

        with patch('app.embeddings._get_model', return_value=mock_model):
            from app.embeddings import embed_text
            result = embed_text("test text")
            assert result.shape[1] == embedding_dim

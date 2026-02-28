"""
Text embedding functionality using SentenceTransformer models.

Provides lazy-loaded embedding generation for semantic search.
"""
from typing import Union

import numpy as np
from numpy.typing import NDArray

try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore[misc, assignment]
    _SENTENCE_TRANSFORMERS_AVAILABLE = False

from .logger import setup_logger
from .exceptions import EmbeddingError
from .config import settings

logger = setup_logger(__name__)

_model: Union["SentenceTransformer", None] = None
MODEL_NAME: str = settings.EMBEDDING_MODEL


def _get_model() -> "SentenceTransformer":
    """
    Get or initialize the embedding model (lazy loading).
    
    Returns:
        Initialized SentenceTransformer model
        
    Raises:
        EmbeddingError: If model loading fails or sentence_transformers not installed
    """
    global _model
    if _model is None:
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            raise EmbeddingError(
                "sentence-transformers is not installed. Install with: pip install sentence-transformers",
                details={"model": MODEL_NAME}
            )
        try:
            logger.info(f"Loading embedding model: {MODEL_NAME}")
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}", exc_info=True)
            raise EmbeddingError(
                f"Failed to load embedding model {MODEL_NAME}",
                details={"error": str(e)}
            )
    return _model


def embed_text(texts: Union[str, list[str]]) -> NDArray[np.float32]:
    """
    Generate embeddings for input text(s).
    
    Args:
        texts: Single text string or list of text strings to embed
        
    Returns:
        Numpy array of normalized embeddings (shape: [n_texts, embedding_dim])
        
    Raises:
        EmbeddingError: If embedding generation fails
        
    Example:
        >>> embeddings = embed_text(["car won't start", "engine makes noise"])
        >>> embeddings.shape
        (2, 384)
    """
    try:
        model = _get_model()
        
        # Convert single string to list
        if isinstance(texts, str):
            texts = [texts]
            
        if not texts:
            logger.warning("Empty text list provided for embedding")
            return np.array([], dtype=np.float32)
        
        logger.debug(f"Generating embeddings for {len(texts)} text(s)")
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        return embeddings
        
    except EmbeddingError:
        raise
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}", exc_info=True)
        raise EmbeddingError(
            "Failed to generate embeddings",
            details={"error": str(e), "num_texts": len(texts) if isinstance(texts, list) else 1}
        )

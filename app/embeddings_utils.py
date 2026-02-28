"""
Embedding utility functions for consistent embedding generation across modules.

Consolidates common embedding patterns to avoid duplication and provide
a single source of truth for embedding operations.
"""
from typing import Union

import numpy as np
from numpy.typing import NDArray

from .embeddings import embed_text
from .logger import setup_logger
from .exceptions import EmbeddingError

logger = setup_logger(__name__)


def embed_query(text: str) -> NDArray[np.float32]:
    """
    Embed a single query string for semantic search.

    Handles the common pattern of embedding a single text and extracting
    the first (and only) result. Used for query embedding in retrieval
    and prediction tasks.

    Args:
        text: Query text to embed (e.g., symptoms, search terms)

    Returns:
        Single embedding vector of shape (384,)

    Raises:
        EmbeddingError: If embedding generation fails

    Example:
        >>> query_vec = embed_query("car won't start")
        >>> query_vec.shape
        (384,)
    """
    if not text or not text.strip():
        logger.warning("Empty text provided to embed_query")
        raise EmbeddingError(
            "Cannot embed empty text",
            details={"text": text}
        )

    try:
        # embed_text returns (n, 384) - extract first row
        embeddings = embed_text([text])
        return embeddings[0]
    except EmbeddingError:
        raise
    except Exception as e:
        logger.error(f"Failed to embed query: {str(e)}", exc_info=True)
        raise EmbeddingError(
            "Failed to embed query text",
            details={"error": str(e), "text_length": len(text)}
        )


def ensure_embedding_vector(
    embedding: Union[NDArray[np.float32], list, tuple],
    expected_dim: int = 384
) -> NDArray[np.float32]:
    """
    Ensure embedding is a normalized numpy array of correct dimension.

    Handles type conversion from list/tuple to numpy, and validates/
    normalizes dimensions.

    Args:
        embedding: Embedding as numpy array, list, or tuple
        expected_dim: Expected embedding dimension (default: 384)

    Returns:
        Numpy array of correct shape (expected_dim,)

    Raises:
        ValueError: If embedding dimension doesn't match expected

    Example:
        >>> emb_list = [0.1, 0.2, ..., 0.3]  # 384 elements
        >>> vec = ensure_embedding_vector(emb_list)
        >>> vec.shape
        (384,)
    """
    # Convert to numpy if needed
    if isinstance(embedding, (list, tuple)):
        embedding = np.array(embedding, dtype=np.float32)
    elif not isinstance(embedding, np.ndarray):
        raise ValueError(
            f"Invalid embedding type: {type(embedding)}. "
            f"Expected numpy array, list, or tuple"
        )

    # Ensure float32 dtype
    if embedding.dtype != np.float32:
        embedding = embedding.astype(np.float32)

    # Validate dimension
    if len(embedding) != expected_dim:
        raise ValueError(
            f"Invalid embedding dimension: {len(embedding)}, "
            f"expected {expected_dim}"
        )

    return embedding

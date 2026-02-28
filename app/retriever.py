"""
Document retrieval functionality.

Retrieve relevant diagnostic manual passages based on semantic similarity
to customer symptoms.
"""
from typing import Any

from numpy.typing import NDArray
import numpy as np

from .embeddings_utils import embed_query
from .vector_store import search
from .logger import setup_logger
from .exceptions import RetrievalError

logger = setup_logger(__name__)


def retrieve(symptoms: str, top_k: int = 10) -> list[dict[str, Any]]:
    """
    Retrieve relevant diagnostic documents for given symptoms.
    
    Args:
        symptoms: Customer-reported symptoms and diagnostic codes
        top_k: Number of top documents to retrieve (default: 10)
        
    Returns:
        List of metadata dictionaries for the most relevant documents
        
    Raises:
        RetrievalError: If retrieval fails
        
    Example:
        >>> docs = retrieve("car won't start, P0300 code")
        >>> len(docs)
        10
    """
    if not symptoms or not symptoms.strip():
        logger.warning("Empty symptoms provided for retrieval")
        return []
    
    try:
        logger.info(f"Retrieving documents for symptoms (length: {len(symptoms)})")
        
        # Generate embedding for query
        vec: NDArray[np.float32] = embed_query(symptoms)
        
        # Search vector store
        results = search(vec, top_k=top_k)
        
        logger.info(f"Retrieved {len(results)} documents")
        return results
        
    except Exception as e:
        logger.error(f"Retrieval failed: {str(e)}", exc_info=True)
        raise RetrievalError(
            "Failed to retrieve documents",
            details={"error": str(e), "symptoms_length": len(symptoms)}
        )

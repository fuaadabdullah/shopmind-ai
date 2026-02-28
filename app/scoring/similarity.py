"""
Semantic similarity module for diagnostic scoring.

Provides semantic similarity scoring using vector embeddings and cosine similarity.
"""
import numpy as np
from numpy.typing import NDArray
from typing import Any

from ..embeddings import embed_text
from ..vector_store import get_vector_store
from ..logger import setup_logger

logger = setup_logger(__name__)


def compute_semantic_similarity(
    query_text: str,
    top_k: int = 5
) -> list[dict[str, Any]]:
    """
    Compute semantic similarity between query and knowledge base.
    
    Embeds the query text and searches the vector store for similar
    diagnostic passages. Returns candidates with semantic similarity scores.
    
    Args:
        query_text: The diagnostic query (symptoms, OBD codes, etc.)
        top_k: Number of top results to retrieve
        
    Returns:
        List of candidate documents with semantic scores
        
    Example:
        >>> results = compute_semantic_similarity("Engine misfiring at idle P0300")
        >>> len(results)
        5
        >>> results[0]["semantic_score"]
        0.85
    """
    try:
        logger.debug(f"Computing semantic similarity for query: {query_text[:50]}...")
        
        # Generate embedding for query
        query_embeddings = embed_text([query_text])
        
        if len(query_embeddings) == 0:
            logger.warning("No embedding generated for query")
            return []
        
        query_vector = query_embeddings[0]
        
        # Search vector store
        store = get_vector_store()
        results = store.search(query_vector, top_k=top_k)
        
        # Calculate and attach similarity scores
        scored_candidates = []
        for r in results:
            # Get the stored vector for accurate similarity calculation
            # Since FAISS returns normalized scores, we use that
            vector = r.get("vector")
            if vector is not None:
                score = cosine_similarity(query_vector, vector)
            else:
                # Fallback: use the score from the search result
                score = r.get("score", 0.0)
            
            scored_candidates.append({
                "text": r.get("text", ""),
                "metadata": r.get("metadata", {}),
                "semantic_score": float(score),
                "source": r.get("source", "unknown")
            })
        
        logger.debug(f"Found {len(scored_candidates)} semantic matches")
        return scored_candidates
        
    except Exception as e:
        logger.error(f"Semantic similarity computation failed: {str(e)}", exc_info=True)
        return []


def cosine_similarity(a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    # Handle zero vectors
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))


def batch_compute_similarity(
    queries: list[str],
    top_k: int = 5
) -> list[list[dict[str, Any]]]:
    """
    Compute semantic similarity for multiple queries.
    
    More efficient than calling compute_semantic_similarity multiple times
    as it batches the embedding generation.
    
    Args:
        queries: List of diagnostic queries
        top_k: Number of top results per query
        
    Returns:
        List of result lists, one per query
    """
    try:
        # Batch embed all queries
        query_embeddings = embed_text(queries)
        
        store = get_vector_store()
        all_results = []
        
        for query_vector in query_embeddings:
            results = store.search(query_vector, top_k=top_k)
            
            scored = []
            for r in results:
                vector = r.get("vector")
                if vector is not None:
                    score = cosine_similarity(query_vector, vector)
                else:
                    score = r.get("score", 0.0)
                    
                scored.append({
                    "text": r.get("text", ""),
                    "metadata": r.get("metadata", {}),
                    "semantic_score": float(score),
                    "source": r.get("source", "unknown")
                })
            
            all_results.append(scored)
        
        return all_results
        
    except Exception as e:
        logger.error(f"Batch similarity computation failed: {str(e)}", exc_info=True)
        return [[] for _ in queries]

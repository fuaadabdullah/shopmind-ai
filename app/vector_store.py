"""FAISS-based vector store for semantic search.

Provides thread-safe vector indexing and similarity search for diagnostic
manual passages. Uses singleton pattern to manage global index state.
"""
import os
import pickle
import threading
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray
import faiss

from .logger import setup_logger
from .exceptions import VectorStoreError
from .metrics import faiss_search_latency_seconds, faiss_search_total

logger = setup_logger(__name__)

INDEX_PATH = "data/faiss_index/index.bin"
META_PATH = "data/faiss_index/meta.pkl"
DIMENSION = 384


class VectorStore:
    """Thread-safe FAISS vector store singleton."""
    
    _instance: Optional['VectorStore'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'VectorStore':
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the vector store (only once)."""
        if self._initialized:
            return
            
        self._write_lock: threading.Lock = threading.Lock()
        self.index: Optional[faiss.Index] = None
        self.metadata: list[dict[str, Any]] = []
        
        try:
            self._load_index()
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {str(e)}", exc_info=True)
            # Initialize empty index as fallback
            self.index = faiss.IndexFlatIP(DIMENSION)
            self.metadata = []
            self._initialized = True
            logger.warning("Initialized empty vector store as fallback")
    
    def _load_index(self) -> None:
        """Load existing index and metadata from disk."""
        if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
            try:
                logger.info(f"Loading FAISS index from {INDEX_PATH}")
                self.index = faiss.read_index(INDEX_PATH)

                with open(META_PATH, "rb") as f:
                    self.metadata = pickle.load(f)

                logger.info(
                    f"Loaded index with {self.index.ntotal} vectors and "
                    f"{len(self.metadata)} metadata entries"
                )
            except Exception as e:
                logger.error(f"Failed to load index: {str(e)}", exc_info=True)
                raise VectorStoreError(
                    "Failed to load FAISS index",
                    details={"error": str(e), "path": INDEX_PATH}
                )
        else:
            logger.info("No existing index found, creating new empty index")
            self.index = faiss.IndexFlatIP(DIMENSION)
            self.metadata = []
    
    def add_embeddings(
        self,
        vectors: NDArray[np.float32],
        metas: list[dict[str, Any]]
    ) -> None:
        """
        Add embeddings and associated metadata to the index.

        Args:
            vectors: Numpy array of embedding vectors (shape: [n, dimension])
            metas: List of metadata dictionaries, one per vector

        Raises:
            VectorStoreError: If adding embeddings fails
        """
        if len(vectors) != len(metas):
            raise VectorStoreError(
                "Vector and metadata count mismatch",
                details={"vectors": len(vectors), "metadata": len(metas)}
            )

        with self._write_lock:
            try:
                logger.debug(f"Adding {len(vectors)} vectors to index")
                self.index.add(np.asarray(vectors, dtype=np.float32))
                self.metadata.extend(metas)

                # Persist to disk
                os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
                faiss.write_index(self.index, INDEX_PATH)

                with open(META_PATH, "wb") as f:
                    pickle.dump(self.metadata, f)

                logger.info(
                    f"Successfully added {len(vectors)} vectors. "
                    f"Total vectors: {self.index.ntotal}"
                )
            except Exception as e:
                logger.error(f"Failed to add embeddings: {str(e)}", exc_info=True)
                raise VectorStoreError(
                    "Failed to add embeddings to index",
                    details={"error": str(e), "num_vectors": len(vectors)}
                )
    
    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors in the index.

        Args:
            query_vector: Query embedding vector (shape: [dimension])
            top_k: Number of top results to return

        Returns:
            List of metadata dictionaries for the top-k most similar vectors

        Raises:
            VectorStoreError: If search fails
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search called on empty index")
            faiss_search_total.labels(method="search", status="empty_index").inc()
            return []

        try:
            # Ensure query vector is 2D array
            query_array = np.asarray([query_vector], dtype=np.float32)

            logger.debug(f"Searching for top {top_k} results")

            # Time the FAISS search operation
            with faiss_search_latency_seconds.labels(method="search", status="success").time():
                _, indices = self.index.search(query_array, top_k)

            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self.metadata):
                    results.append(self.metadata[idx])
                else:
                    logger.warning(f"Invalid index {idx} returned from search")

            faiss_search_total.labels(method="search", status="success").inc()
            logger.debug(f"Found {len(results)} results")
            return results

        except Exception as e:
            faiss_search_total.labels(method="search", status="error").inc()
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            raise VectorStoreError(
                "Failed to search index",
                details={"error": str(e), "top_k": top_k}
            )


# Global instance (lazy initialized on first access)
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


# Convenience functions for backward compatibility
def add_embeddings(vectors: NDArray[np.float32], metas: list[dict[str, Any]]) -> None:
    """Add embeddings to the global vector store."""
    get_vector_store().add_embeddings(vectors, metas)


def search(query_vector: NDArray[np.float32], top_k: int = 5) -> list[dict[str, Any]]:
    """Search the global vector store."""
    return get_vector_store().search(query_vector, top_k)

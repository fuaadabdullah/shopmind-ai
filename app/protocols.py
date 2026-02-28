"""Protocol definitions for ShopMindAI interfaces."""
from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed_text(self, texts: str | list[str]) -> NDArray[np.float32]:
        """Generate embeddings for input text(s)."""


class VectorStoreProtocol(Protocol):
    """Protocol for vector store implementations."""

    def add_embeddings(
        self,
        vectors: NDArray[np.float32],
        metas: list[dict[str, object]],
    ) -> None:
        """Add embeddings with metadata to the store."""

    def search(self, query_vector: NDArray[np.float32], top_k: int = 5) -> list[dict[str, object]]:
        """Search for similar vectors and return metadata."""


class ScoreCalculator(Protocol):
    """Protocol for scoring implementations."""

    def score(self, query: str, candidates: list[dict[str, object]]) -> list[dict[str, object]]:
        """Score and rank candidates for a query."""

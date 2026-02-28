from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.scoring.similarity import (
    batch_compute_similarity,
    compute_semantic_similarity,
    cosine_similarity,
)


def test_cosine_similarity_zero_vector_returns_zero():
    assert cosine_similarity(
        np.zeros(3, dtype=np.float32),
        np.array([1.0, 0.0, 0.0], dtype=np.float32),
    ) == pytest.approx(0.0)
    assert cosine_similarity(
        np.array([1.0, 0.0, 0.0], dtype=np.float32),
        np.zeros(3, dtype=np.float32),
    ) == pytest.approx(0.0)


def test_cosine_similarity_same_vector_is_one():
    vector = np.array([0.5, 0.5], dtype=np.float32)

    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_compute_semantic_similarity_scores_candidates():
    query_vector = np.array([1.0, 0.0], dtype=np.float32)
    result_vector = np.array([1.0, 0.0], dtype=np.float32)

    with patch("app.scoring.similarity.embed_text") as mock_embed, patch(
        "app.scoring.similarity.get_vector_store"
    ) as mock_store:
        mock_embed.return_value = [query_vector]

        store = MagicMock()
        store.search.return_value = [
            {
                "text": "Battery issue",
                "metadata": {"id": 1},
                "vector": result_vector,
                "source": "kb",
            },
            {
                "text": "Starter issue",
                "metadata": {"id": 2},
                "score": 0.42,
                "source": "kb2",
            },
        ]
        mock_store.return_value = store

        results = compute_semantic_similarity("car won't start", top_k=2)

    assert len(results) == 2
    assert results[0]["semantic_score"] == pytest.approx(1.0)
    assert results[1]["semantic_score"] == pytest.approx(0.42)


def test_compute_semantic_similarity_empty_embedding_returns_empty_list():
    with patch("app.scoring.similarity.embed_text") as mock_embed:
        mock_embed.return_value = []
        assert compute_semantic_similarity("query") == []


def test_compute_semantic_similarity_handles_exception():
    with patch("app.scoring.similarity.embed_text") as mock_embed:
        mock_embed.side_effect = RuntimeError("boom")
        assert compute_semantic_similarity("query") == []


def test_batch_compute_similarity_returns_results_per_query():
    query_vectors = [
        np.array([1.0, 0.0], dtype=np.float32),
        np.array([0.0, 1.0], dtype=np.float32),
    ]

    with patch("app.scoring.similarity.embed_text") as mock_embed, patch(
        "app.scoring.similarity.get_vector_store"
    ) as mock_store:
        mock_embed.return_value = query_vectors

        store = MagicMock()
        store.search.side_effect = [
            [
                {
                    "text": "A",
                    "metadata": {},
                    "vector": np.array([1.0, 0.0], dtype=np.float32),
                }
            ],
            [
                {
                    "text": "B",
                    "metadata": {},
                    "score": 0.5,
                }
            ],
        ]
        mock_store.return_value = store

        results = batch_compute_similarity(["q1", "q2"], top_k=1)

    assert len(results) == 2
    assert results[0][0]["semantic_score"] == pytest.approx(1.0)
    assert results[1][0]["semantic_score"] == pytest.approx(0.5)


def test_batch_compute_similarity_handles_errors():
    with patch("app.scoring.similarity.embed_text") as mock_embed:
        mock_embed.side_effect = ValueError("nope")
        results = batch_compute_similarity(["q1", "q2"], top_k=1)

    assert results == [[], []]

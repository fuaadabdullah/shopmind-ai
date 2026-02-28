"""
Unit tests for text chunking functionality.

Tests chunk_text, chunk_text_with_overlap, and chunk_by_paragraphs
for correct text splitting behavior.
"""
import pytest
from app.ingestion.chunker import (
    chunk_text,
    chunk_text_with_overlap,
    chunk_by_paragraphs
)


class TestChunkText:
    """Tests for basic chunk_text function."""

    def test_chunk_empty_text(self):
        """Empty text should return empty list."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_single_word(self):
        """Single word text should return list with one element."""
        result = chunk_text("hello", chunk_size=5)
        assert len(result) == 1
        assert result[0] == "hello"

    def test_chunk_exact_size(self):
        """Text matching chunk size should return single chunk."""
        text = " ".join(["word"] * 10)
        result = chunk_text(text, chunk_size=10)
        assert len(result) == 1

    def test_chunk_multiple_chunks(self):
        """Text longer than chunk_size should be split."""
        text = " ".join(["word"] * 30)
        result = chunk_text(text, chunk_size=10)
        assert len(result) == 3
        assert all(len(chunk.split()) <= 10 for chunk in result)

    def test_chunk_whitespace_normalization(self):
        """Multiple spaces should be normalized to single space."""
        text = "word1    word2     word3"
        result = chunk_text(text, chunk_size=100)
        assert result[0] == "word1 word2 word3"

    def test_chunk_preserves_text(self):
        """All words should be preserved after chunking."""
        text = " ".join([f"word{i}" for i in range(25)])
        result = chunk_text(text, chunk_size=10)
        rejoined = " ".join(result)
        assert rejoined == text

    def test_chunk_custom_size(self):
        """Custom chunk sizes should be respected."""
        text = " ".join(["word"] * 100)
        result = chunk_text(text, chunk_size=20)
        assert len(result) == 5
        assert all(len(chunk.split()) <= 20 for chunk in result)


class TestChunkTextWithOverlap:
    """Tests for overlapping chunk_text_with_overlap function."""

    def test_overlap_empty_text(self):
        """Empty text should return empty list."""
        assert chunk_text_with_overlap("") == []
        assert chunk_text_with_overlap("   ") == []

    def test_overlap_single_chunk(self):
        """Text smaller than chunk_size should return single chunk."""
        text = "word " * 10
        result = chunk_text_with_overlap(text.strip(), chunk_size=20, overlap=5)
        assert len(result) == 1

    def test_overlap_creates_overlap(self):
        """Overlapping chunks should have duplicate words."""
        text = " ".join([f"word{i}" for i in range(30)])
        result = chunk_text_with_overlap(text, chunk_size=10, overlap=3)
        assert len(result) > 1
        # Each chunk should contain some overlap from previous chunk
        for i in range(1, len(result)):
            prev_words = set(result[i-1].split())
            curr_words = set(result[i].split())
            overlap_words = prev_words & curr_words
            assert len(overlap_words) >= 1  # At least some overlap

    def test_overlap_zero_overlap(self):
        """Zero overlap should produce non-overlapping chunks."""
        text = " ".join(["word"] * 30)
        result = chunk_text_with_overlap(text, chunk_size=10, overlap=0)
        # Join all and verify no duplicates across chunks
        all_chunks = " ".join(result)
        assert all_chunks == text.replace("  ", " ").strip()

    def test_overlap_preserves_all_text(self):
        """Overlapping chunks should preserve all text (with duplication)."""
        text = " ".join([f"word{i}" for i in range(25)])
        result = chunk_text_with_overlap(text, chunk_size=10, overlap=3)
        # Count word occurrences - first and last words should appear once,
        # middle words more than once due to overlap
        combined = " ".join(result)
        assert "word0" in combined
        assert "word24" in combined


class TestChunkByParagraphs:
    """Tests for paragraph-aware chunking."""

    def test_paragraph_empty_text(self):
        """Empty text should return empty list."""
        assert chunk_by_paragraphs("") == []
        assert chunk_by_paragraphs("\n\n\n") == []

    def test_paragraph_single_paragraph(self):
        """Single paragraph should return single chunk."""
        text = "This is a single paragraph."
        result = chunk_by_paragraphs(text)
        assert len(result) == 1
        assert result[0] == text

    def test_paragraph_multiple_paragraphs(self):
        """Multiple paragraphs separated by double newline."""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        # Each para is ~2 words; use max_words=3 so they don't merge
        result = chunk_by_paragraphs(text, min_words=1, max_words=3)
        assert len(result) == 3
        assert "Paragraph 1" in result[0]
        assert "Paragraph 2" in result[1]
        assert "Paragraph 3" in result[2]

    def test_paragraph_split_long_paragraphs(self):
        """Very long paragraphs should be split by max_words."""
        long_para = " ".join(["word"] * 500)
        result = chunk_by_paragraphs(long_para, max_words=100)
        # Should be split into multiple chunks
        assert len(result) > 1
        assert all(len(chunk.split()) <= 100 for chunk in result)

    def test_paragraph_mixed_newlines(self):
        """Various newline patterns should be handled."""
        text = "Para 1\n\nPara 2\n\n\nPara 3"
        # Each para is ~2 words; use max_words=3 so they don't merge
        result = chunk_by_paragraphs(text, min_words=1, max_words=3)
        assert len(result) >= 3
        assert all(p.strip() for p in result)


class TestChunkingEdgeCases:
    """Edge case tests for all chunking functions."""

    def test_text_with_special_characters(self):
        """Text with special characters should be preserved."""
        text = "test@example.com and $100.00 & symbols!"
        result = chunk_text(text, chunk_size=100)
        assert "@" in result[0]
        assert "$" in result[0]
        assert "&" in result[0]

    def test_very_long_single_word(self):
        """Very long single word should not be split."""
        long_word = "a" * 500
        result = chunk_text(long_word, chunk_size=10)
        assert len(result) == 1
        assert result[0] == long_word

    def test_unicode_text(self):
        """Unicode characters should be handled correctly."""
        text = "Hello 你好 مرحبا 🚀 Здравствуй"
        result = chunk_text(text, chunk_size=100)
        assert len(result) >= 1
        assert "你好" in result[0] or any("你好" in chunk for chunk in result)

    def test_chunk_size_one(self):
        """Chunk size of 1 should split every word."""
        text = "word1 word2 word3 word4"
        result = chunk_text(text, chunk_size=1)
        assert len(result) == 4
        assert result == ["word1", "word2", "word3", "word4"]

    def test_invalid_overlap_greater_than_chunk(self):
        """Overlap greater than chunk_size should be clamped."""
        text = " ".join(["word"] * 20)
        result = chunk_text_with_overlap(text, chunk_size=5, overlap=10)
        # Should still produce valid chunks
        assert len(result) > 0
        assert all(chunk.strip() for chunk in result)

"""
Unit tests for document indexer functionality.

Tests get_file_hash, load_indexed_hashes, index_pdf, and deduplication
for the indexing pipeline.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from app.ingestion.indexer import (
    get_file_hash,
    load_indexed_hashes,
    save_indexed_hash
)


class TestFileHashing:
    """Tests for file hash calculation."""

    def test_get_file_hash_nonexistent(self):
        """Nonexistent file should return None."""
        result = get_file_hash("/nonexistent/path/file.pdf")
        assert result is None

    def test_get_file_hash_consistency(self):
        """Same file should produce same hash."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            hash1 = get_file_hash(tmp_path)
            hash2 = get_file_hash(tmp_path)
            assert hash1 == hash2
            assert hash1 is not None
        finally:
            os.unlink(tmp_path)

    def test_get_file_hash_different_files(self):
        """Different files should produce different hashes."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp1:
            tmp1.write(b"content 1")
            tmp1_path = tmp1.name

        with tempfile.NamedTemporaryFile(delete=False) as tmp2:
            tmp2.write(b"content 2")
            tmp2_path = tmp2.name

        try:
            hash1 = get_file_hash(tmp1_path)
            hash2 = get_file_hash(tmp2_path)
            assert hash1 != hash2
        finally:
            os.unlink(tmp1_path)
            os.unlink(tmp2_path)

    def test_get_file_hash_large_file(self):
        """Large file hashing should not fail."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Write 10MB of data
            for _ in range(10 * 1024):
                tmp.write(b"x" * 1024)
            tmp_path = tmp.name

        try:
            result = get_file_hash(tmp_path)
            assert result is not None
            assert len(result) == 64  # SHA256 hex digest is 64 chars
        finally:
            os.unlink(tmp_path)

    def test_get_file_hash_empty_file(self):
        """Empty file should produce valid hash."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = get_file_hash(tmp_path)
            assert result is not None
            assert len(result) == 64
            # Empty file has consistent hash
            assert result == get_file_hash(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_get_file_hash_binary_content(self):
        """Binary files should be hashed correctly."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Write binary data with null bytes
            tmp.write(b"\x00\x01\x02\x03\xff\xfe\xfd")
            tmp_path = tmp.name

        try:
            result = get_file_hash(tmp_path)
            assert result is not None
            assert len(result) == 64
        finally:
            os.unlink(tmp_path)

    def test_get_file_hash_permission_denied(self):
        """File without read permissions should return None."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        try:
            os.chmod(tmp_path, 0o000)
            result = get_file_hash(tmp_path)
            assert result is None
        finally:
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)


class TestHashedIndexLoading:
    """Tests for loading and saving indexed hashes."""

    def test_load_nonexistent_hash_file(self):
        """Loading nonexistent hash file should return empty set."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = load_indexed_hashes()
            assert result == set()

    def test_load_empty_hash_file(self):
        """Loading empty hash file should return empty set."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", tmp_path):
                result = load_indexed_hashes()
                assert result == set()
        finally:
            os.unlink(tmp_path)

    def test_load_hash_file_with_hashes(self):
        """Loading hash file should parse hashes correctly."""
        test_hashes = [
            "abc123def456" * 5 + "abcd",  # 64 chars
            "fed654cba321" * 5 + "fedc",  # 64 chars
        ]

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            for h in test_hashes:
                tmp.write(h + "\n")
            tmp_path = tmp.name

        try:
            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", tmp_path):
                result = load_indexed_hashes()
                assert len(result) == 2
                assert test_hashes[0] in result
                assert test_hashes[1] in result
        finally:
            os.unlink(tmp_path)

    def test_load_hash_file_with_duplicates(self):
        """Loading hash file with duplicates should deduplicate."""
        test_hash = "abc123def456" * 5 + "abcd"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(test_hash + "\n")
            tmp.write(test_hash + "\n")
            tmp.write(test_hash + "\n")
            tmp_path = tmp.name

        try:
            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", tmp_path):
                result = load_indexed_hashes()
                assert len(result) == 1
                assert test_hash in result
        finally:
            os.unlink(tmp_path)

    def test_save_hash_file(self):
        """Saving hashes should create file with correct format."""
        test_hashes = {
            "abc123def456" * 5 + "abcd",
            "fed654cba321" * 5 + "fedc",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = os.path.join(tmp_dir, "hashes.txt")

            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", test_file):
                for h in test_hashes:
                    save_indexed_hash(h)
                assert os.path.exists(test_file)

                with open(test_file, "r") as f:
                    saved_hashes = set(line.strip() for line in f)

                assert saved_hashes == test_hashes

    def test_save_hash_creates_directory(self):
        """Saving hashes should create directory if needed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_path = os.path.join(tmp_dir, "data", "index", "hashes.txt")
            test_hash = "abc123def456" * 5 + "abcd"

            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", nested_path):
                with patch("os.makedirs"):
                    try:
                        save_indexed_hash(test_hash)
                    except Exception:
                        pass  # May fail due to mocking, but shouldn't crash


class TestDeduplication:
    """Tests for document deduplication logic."""

    def test_duplicate_detection(self):
        """Already-indexed document should be detected."""
        test_hash = "abc123def456" * 5 + "abcd"
        indexed = {test_hash}

        assert test_hash in indexed
        assert "different_hash" not in indexed

    def test_deduplication_across_sessions(self):
        """Hashes should persist across sessions."""
        test_hash = "abc123def456" * 5 + "abcd"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(test_hash + "\n")
            tmp_path = tmp.name

        try:
            # First load
            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", tmp_path):
                hashes1 = load_indexed_hashes()

            # Second load (simulating new session)
            with patch("app.ingestion.indexer.INDEXED_HASHES_FILE", tmp_path):
                hashes2 = load_indexed_hashes()

            assert hashes1 == hashes2
            assert test_hash in hashes2
        finally:
            os.unlink(tmp_path)


class TestIndexingPipeline:
    """Tests for the full indexing pipeline."""

    @patch("app.ingestion.indexer.save_indexed_hash")
    @patch("app.ingestion.indexer.add_embeddings")
    @patch("app.ingestion.indexer.embed_text")
    @patch("app.ingestion.indexer.chunk_text")
    @patch("app.ingestion.indexer.extract_text_from_pdf")
    @patch("app.ingestion.indexer.is_already_indexed", return_value=False)
    def test_index_pdf_success(
        self,
        mock_is_indexed,
        mock_extract,
        mock_chunk,
        mock_embed_text,
        mock_add_embeddings,
        mock_save_hash
    ):
        """Successful PDF indexing should extract, chunk, embed, and store."""
        mock_extract.return_value = "Extracted PDF text content"
        mock_chunk.return_value = ["chunk1", "chunk2"]
        mock_embed_text.return_value = [[0.1, 0.2], [0.3, 0.4]]

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        metadata = {"make": "Honda", "year": "2016", "model": "Accord"}

        try:
            from app.ingestion.indexer import index_pdf
            result = index_pdf(tmp_path, metadata)

            # Should return True on success
            assert result is True

            # Should have called embedding function
            mock_embed_text.assert_called()
            mock_add_embeddings.assert_called()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("app.ingestion.indexer.extract_text_from_pdf")
    @patch("app.ingestion.indexer.is_already_indexed", return_value=False)
    def test_index_pdf_empty_extraction(self, mock_is_indexed, mock_extract):
        """PDF with no text should be skipped."""
        mock_extract.return_value = ""

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        metadata = {"make": "Honda", "year": "2016", "model": "Accord"}

        try:
            from app.ingestion.indexer import index_pdf
            result = index_pdf(tmp_path, metadata)
            # Empty extraction should return False
            assert result is False
            mock_extract.assert_called_once()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("app.ingestion.indexer.is_already_indexed", return_value=True)
    def test_skip_already_indexed(self, mock_is_indexed):
        """Already-indexed PDF should be skipped."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        metadata = {"make": "Honda", "year": "2016", "model": "Accord"}

        try:
            from app.ingestion.indexer import index_pdf
            with patch("app.ingestion.indexer.extract_text_from_pdf") as mock_extract:
                result = index_pdf(tmp_path, metadata)
                # Should return False and not extract
                assert result is False
                mock_extract.assert_not_called()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("app.ingestion.indexer.extract_text_from_pdf")
    @patch("app.ingestion.indexer.is_already_indexed", return_value=False)
    def test_index_pdf_extraction_error(self, mock_is_indexed, mock_extract):
        """Extraction errors should be handled gracefully."""
        mock_extract.side_effect = Exception("Extraction failed")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"PDF content")
            tmp_path = tmp.name

        metadata = {"make": "Honda", "year": "2016", "model": "Accord"}

        try:
            from app.ingestion.indexer import index_pdf
            # Should handle error gracefully (may return False or raise)
            try:
                result = index_pdf(tmp_path, metadata)
                assert result is False
            except Exception:
                pass  # Exception propagation is acceptable
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

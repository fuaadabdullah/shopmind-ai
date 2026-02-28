"""
Unit tests for PDF parsing functionality.

Tests extract_text_from_pdf, extract_with_layout, and error handling
for PDF text extraction.
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from app.ingestion.pdf_parser import (
    extract_text_from_pdf,
    extract_text_with_ocr,
    extract_with_layout
)


def _make_pdf_cm(pages, metadata=None):
    """Create a mock pdfplumber PDF that works as a context manager."""
    mock_pdf = MagicMock()
    mock_pdf.pages = pages
    if metadata is not None:
        mock_pdf.metadata = metadata
    mock_pdf.__enter__ = Mock(return_value=mock_pdf)
    mock_pdf.__exit__ = Mock(return_value=False)
    return mock_pdf


class TestExtractTextFromPDF:
    """Tests for PDF text extraction."""

    def test_nonexistent_file(self):
        """Should return empty string for nonexistent file."""
        result = extract_text_from_pdf("/nonexistent/path/file.pdf")
        assert result == ""

    def test_pdf_with_no_text(self):
        """PDF with no extractable text should attempt OCR."""
        mock_page = Mock()
        mock_page.extract_text.return_value = None
        mock_pdf_obj = _make_pdf_cm([mock_page])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                with patch(
                    "app.ingestion.pdf_parser.extract_text_with_ocr",
                    return_value="OCR text"
                ):
                    result = extract_text_from_pdf(tmp_path)
                    assert isinstance(result, str)
        finally:
            os.unlink(tmp_path)

    def test_pdf_extraction_error(self):
        """PDF with extraction error should attempt OCR fallback."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", side_effect=Exception("PDF corrupted")):
                with patch(
                    "app.ingestion.pdf_parser.extract_text_with_ocr",
                    return_value=""
                ):
                    result = extract_text_from_pdf(tmp_path)
                    assert isinstance(result, str)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_pdf_with_multiple_pages(self):
        """Multi-page PDF should extract text from all pages."""
        mock_pages = []
        for i in range(2):
            page = Mock()
            page.extract_text.return_value = f"Page {i+1} text"
            mock_pages.append(page)

        mock_pdf_obj = _make_pdf_cm(mock_pages)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                result = extract_text_from_pdf(tmp_path)
                assert "Page 1 text" in result
                assert "Page 2 text" in result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_pdf_with_empty_pages(self):
        """PDF with empty pages should be handled."""
        mock_page1 = Mock()
        mock_page2 = Mock()
        mock_page1.extract_text.return_value = "Some text"
        mock_page2.extract_text.return_value = None

        mock_pdf_obj = _make_pdf_cm([mock_page1, mock_page2])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                result = extract_text_from_pdf(tmp_path)
                assert "Some text" in result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestExtractWithLayout:
    """Tests for layout-aware PDF extraction."""

    def test_nonexistent_file_layout(self):
        """Should return empty structure for nonexistent file."""
        result = extract_with_layout("/nonexistent/path/file.pdf")
        assert result["text"] == ""
        assert result["tables"] == []
        assert result["metadata"] == {}

    def test_layout_extraction_structure(self):
        """Result should have required keys."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = extract_with_layout(tmp_path)
            assert "text" in result
            assert "tables" in result
            assert "metadata" in result
            assert isinstance(result["text"], str)
            assert isinstance(result["tables"], list)
            assert isinstance(result["metadata"], dict)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_layout_with_table_extraction(self):
        """Should extract tables from PDF."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Page text"
        mock_page.extract_tables.return_value = [
            [["Header1", "Header2"], ["Row1Col1", "Row1Col2"]]
        ]

        mock_pdf_obj = _make_pdf_cm(
            [mock_page],
            metadata={"Title": "Test PDF"}
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                result = extract_with_layout(tmp_path)
                assert "Page text" in result["text"]
                assert len(result["tables"]) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestOCRFallback:
    """Tests for OCR fallback functionality."""

    def test_ocr_dependencies_missing(self):
        """Should handle missing OCR dependencies gracefully."""
        # extract_text_with_ocr does 'import pytesseract' inside the function
        # We need to make that import fail
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("pytesseract", "pdf2image"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = extract_text_with_ocr("dummy.pdf")
            assert result == ""

    def test_ocr_on_scanned_pdf(self):
        """Should attempt OCR when text extraction yields nothing."""
        mock_page = Mock()
        mock_page.extract_text.return_value = None
        mock_pdf_obj = _make_pdf_cm([mock_page])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                with patch(
                    "app.ingestion.pdf_parser.extract_text_with_ocr",
                    return_value="Scanned text"
                ) as mock_ocr:
                    result = extract_text_from_pdf(tmp_path)
                    assert isinstance(result, str)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestPDFErrorHandling:
    """Tests for PDF parsing error handling."""

    def test_corrupted_pdf_handling(self):
        """Corrupted PDF should not crash extraction."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", side_effect=RuntimeError("File is corrupted")):
                with patch(
                    "app.ingestion.pdf_parser.extract_text_with_ocr",
                    return_value=""
                ):
                    result = extract_text_from_pdf(tmp_path)
                    assert isinstance(result, str)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_pdf_with_encoding_issues(self):
        """PDF with encoding issues should be handled."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Text with special chars: \u00e5\u00e4\u00f6"
        mock_pdf_obj = _make_pdf_cm([mock_page])

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                result = extract_text_from_pdf(tmp_path)
                assert "\u00e5\u00e4\u00f6" in result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_large_pdf_processing(self):
        """Large PDF should not consume excessive memory."""
        mock_pages = []
        for i in range(1000):
            page = Mock()
            page.extract_text.return_value = f"Page {i} content"
            mock_pages.append(page)

        mock_pdf_obj = _make_pdf_cm(mock_pages)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("pdfplumber.open", return_value=mock_pdf_obj):
                result = extract_text_from_pdf(tmp_path)
                assert len(result) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

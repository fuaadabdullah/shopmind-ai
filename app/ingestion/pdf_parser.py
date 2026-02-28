"""
PDF Parser
Text extraction from PDFs using pdfplumber.
Includes fallback for OCR using Tesseract if text extraction fails.
"""
import os
from typing import Any

import pdfplumber


def extract_text_from_pdf(path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        path: Path to the PDF file
    
    Returns:
        Extracted text from all pages
    """
    if not os.path.exists(path):
        print(f"PDF file not found: {path}")
        return ""
    
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        
        # If text is empty, try OCR
        if not text.strip():
            print(f"No text extracted from {path}, attempting OCR...")
            text = extract_text_with_ocr(path)
            
    except Exception as e:
        print(f"Error extracting text from {path}: {e}")
        # Try OCR as fallback
        try:
            text = extract_text_with_ocr(path)
        except Exception as ocr_error:
            print(f"OCR also failed: {ocr_error}")
    
    return text


def extract_text_with_ocr(path: str) -> str:
    """
    Extract text from PDF using Tesseract OCR.
    Requires pytesseract and pillow to be installed.
    
    Args:
        path: Path to the PDF file
    
    Returns:
        Extracted text using OCR
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        print("OCR dependencies not installed (pytesseract, pdf2image)")
        print("Install with: pip install pytesseract pdf2image")
        return ""
    
    text = ""
    try:
        # Convert PDF pages to images
        images = convert_from_path(path)
        
        for page_num, image in enumerate(images, 1):
            # Perform OCR on each page
            page_text = pytesseract.image_to_string(image)
            text += page_text + "\n"
            print(f"OCR completed page {page_num}/{len(images)}")
    
    except Exception as e:
        print(f"Error during OCR: {e}")
    
    return text


def extract_with_layout(path: str) -> dict[str, Any]:
    """
    Extract text with layout information (tables, etc.)
    
    Args:
        path: Path to the PDF file
    
    Returns:
        Dictionary with text, tables, and metadata
    """
    if not os.path.exists(path):
        return {"text": "", "tables": [], "metadata": {}}
    
    result = {
        "text": "",
        "tables": [],
        "metadata": {}
    }
    
    try:
        with pdfplumber.open(path) as pdf:
            result["metadata"] = {
                "num_pages": len(pdf.pages),
                "file_path": path,
                "file_name": os.path.basename(path)
            }
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                page_text = page.extract_text() or ""
                result["text"] += f"[Page {page_num}]\n{page_text}\n\n"
                
                # Extract tables
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        result["tables"].append({
                            "page": page_num,
                            "table": table
                        })
    
    except Exception as e:
        print(f"Error extracting with layout from {path}: {e}")
    
    return result


if __name__ == "__main__":
    # Test extraction
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Extracting text from: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)
        print(f"Extracted {len(text)} characters")
        print(f"First 500 chars:\n{text[:500]}")
    else:
        print("Usage: python pdf_parser.py <pdf_path>")

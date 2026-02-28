"""
Document Processor for PDF parsing, chunking, and embedding.

Handles extraction of text from PDFs, chunking into segments,
and generating embeddings for indexing.
"""
import os

from ..embeddings import embed_text
from ..logger import setup_logger
from ..types import ProcessedDocument
from .chunker import chunk_text, chunk_text_with_overlap
from .pdf_parser import extract_text_from_pdf

logger = setup_logger(__name__)


class DocumentProcessor:
    """
    Processes documents through the pipeline:
    1. Extract text from PDF
    2. Chunk text into segments
    3. Generate embeddings
    """

    def __init__(
        self,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
        use_overlap: bool = True
    ) -> None:
        """
        Initialize document processor.

        Args:
            chunk_size: Number of words per chunk
            chunk_overlap: Number of words to overlap between chunks
            use_overlap: Whether to use overlapping chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_overlap = use_overlap

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If PDF doesn't exist
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Extracting text from: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            logger.warning(f"No text extracted from {pdf_path}")

        return text

    def chunk_document(self, text: str) -> list[str]:
        """
        Chunk text into segments.

        Args:
            text: Raw text to chunk

        Returns:
            List of text chunks

        Raises:
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Text content is empty")

        logger.info(f"Chunking text (chunk_size={self.chunk_size})")

        if self.use_overlap:
            chunks = chunk_text_with_overlap(
                text,
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap
            )
        else:
            chunks = chunk_text(text, chunk_size=self.chunk_size)

        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        """
        Generate embeddings for text chunks using batch processing.

        Args:
            chunks: List of text chunks

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If embedding generation fails
        """
        if not chunks:
            raise ValueError("No chunks to embed")

        logger.info(f"Embedding {len(chunks)} chunks (batch processing)")

        try:
            # Batch embed all chunks at once for efficiency
            embeddings = embed_text(chunks)
            # Convert numpy array to list of lists for compatibility
            embeddings_list = embeddings.tolist()
            logger.info(f"Successfully embedded {len(embeddings_list)} chunks")
            return embeddings_list

        except Exception as e:
            logger.error(f"Failed to embed chunks: {str(e)}")
            raise RuntimeError(
                f"Embedding generation failed: {str(e)}"
            ) from e

    def process(
        self,
        pdf_path: str
    ) -> ProcessedDocument:
        """
        End-to-end document processing pipeline.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with chunks and embeddings

        Raises:
            Exception: If any step fails
        """
        logger.info(f"Starting document processing: {pdf_path}")

        try:
            # Step 1: Extract text
            text = self.extract_text(pdf_path)

            # Step 2: Chunk text
            chunks = self.chunk_document(text)

            # Step 3: Embed chunks
            embeddings = self.embed_chunks(chunks)

            result: ProcessedDocument = {
                "pdf_path": pdf_path,
                "text_extracted": len(text),
                "chunks": chunks,
                "embeddings": embeddings,
                "success": True,
            }

            logger.info(
                f"Document processing complete: "
                f"{len(chunks)} chunks, {len(embeddings)} embeddings"
            )

            return result

        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}", exc_info=True)
            raise

"""
Index Manager for FAISS-based document indexing.

Handles indexing, deduplication, and metadata management.
"""
import hashlib
import os
from typing import Any, Optional

from ..logger import setup_logger
from ..vector_store import add_embeddings
from .document_processor import DocumentProcessor

logger = setup_logger(__name__)


class IndexManager:
    """Manages document indexing to FAISS with deduplication."""

    INDEXED_HASHES_FILE = "data/faiss_index/indexed_hashes.txt"

    def __init__(self, doc_processor: Optional[DocumentProcessor] = None) -> None:
        """
        Initialize index manager.

        Args:
            doc_processor: DocumentProcessor instance (or creates default)
        """
        self.doc_processor = doc_processor or DocumentProcessor()
        self._load_indexed_hashes()

    def _get_file_hash(self, path: str) -> Optional[str]:
        """
        Generate SHA256 hash of a file.

        Args:
            path: Path to file

        Returns:
            Hex digest or None if error
        """
        sha256_hash = hashlib.sha256()

        try:
            with open(path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {path}: {str(e)}")
            return None

    def _load_indexed_hashes(self) -> None:
        """Load previously indexed document hashes."""
        self.indexed_hashes = set()

        if os.path.exists(self.INDEXED_HASHES_FILE):
            try:
                with open(self.INDEXED_HASHES_FILE, "r") as f:
                    for line in f:
                        self.indexed_hashes.add(line.strip())
                logger.info(
                    f"Loaded {len(self.indexed_hashes)} indexed document hashes"
                )
            except Exception as e:
                logger.warning(f"Error loading indexed hashes: {str(e)}")

    def _save_indexed_hash(self, file_hash: str) -> None:
        """Save a document hash to prevent re-indexing."""
        try:
            os.makedirs(os.path.dirname(self.INDEXED_HASHES_FILE), exist_ok=True)
            with open(self.INDEXED_HASHES_FILE, "a") as f:
                f.write(file_hash + "\n")
            self.indexed_hashes.add(file_hash)
        except Exception as e:
            logger.warning(f"Error saving indexed hash: {str(e)}")

    def is_already_indexed(self, pdf_path: str) -> bool:
        """Check if a document has already been indexed."""
        file_hash = self._get_file_hash(pdf_path)
        if file_hash is None:
            return False
        return file_hash in self.indexed_hashes

    def index_pdf(
        self,
        pdf_path: str,
        metadata: dict[str, Any]
    ) -> bool:
        """
        Index a single PDF document.

        Args:
            pdf_path: Path to PDF file
            metadata: Metadata to attach to the document

        Returns:
            True if indexed successfully, False otherwise
        """
        logger.info(f"Indexing PDF: {pdf_path}")

        # Check if already indexed
        if self.is_already_indexed(pdf_path):
            logger.info(f"PDF already indexed, skipping: {pdf_path}")
            return False

        try:
            # Process document
            result = self.doc_processor.process(pdf_path)
            chunks = result["chunks"]
            embeddings = result["embeddings"]

            # Add to FAISS
            add_embeddings(embeddings, chunks, metadata)

            # Save hash to prevent re-indexing
            file_hash = self._get_file_hash(pdf_path)
            if file_hash:
                self._save_indexed_hash(file_hash)

            logger.info(
                f"Successfully indexed {pdf_path}: "
                f"{len(chunks)} chunks, {len(embeddings)} embeddings"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to index {pdf_path}: {str(e)}", exc_info=True)
            return False

    def index_multiple_pdfs(
        self,
        pdf_paths: list[str],
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Index multiple PDF documents.

        Args:
            pdf_paths: List of PDF file paths
            metadata: Metadata to attach to all documents

        Returns:
            Dictionary with success, skipped, failed counts
        """
        logger.info(f"Indexing {len(pdf_paths)} PDFs...")

        results = {
            "success": 0,
            "skipped": 0,
            "failed": 0
        }

        for i, pdf_path in enumerate(pdf_paths, 1):
            logger.info(f"[{i}/{len(pdf_paths)}] Processing {pdf_path}...")

            try:
                if self.index_pdf(pdf_path, metadata):
                    results["success"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                logger.error(f"Error indexing {pdf_path}: {str(e)}")
                results["failed"] += 1

        logger.info(
            f"Batch indexing complete: "
            f"{results['success']} success, "
            f"{results['skipped']} skipped, "
            f"{results['failed']} failed"
        )

        return results

    def index_directory(
        self,
        directory_path: str,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Index all PDFs in a directory.

        Args:
            directory_path: Path to directory
            metadata: Metadata to attach to PDFs

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Indexing directory: {directory_path}")

        if not os.path.exists(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        # Find all PDF files
        pdf_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))

        logger.info(f"Found {len(pdf_files)} PDF files in directory")

        if not pdf_files:
            logger.warning("No PDF files found in directory")
            return {
                "files_found": 0,
                "indexed": 0
            }

        # Index all PDFs
        return self.index_multiple_pdfs(pdf_files, metadata)

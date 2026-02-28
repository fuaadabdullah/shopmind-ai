"""
Indexer
Connects PDF parser + embeddings + FAISS for document indexing.
Includes deduplication using content hashing.
"""
import hashlib
import os
from typing import Any, Optional
from .pdf_parser import extract_text_from_pdf
from .chunker import chunk_text, create_contextual_chunk
from app.embeddings import embed_text
from app.vector_store import add_embeddings


# Track already indexed document hashes to avoid duplicates
INDEXED_HASHES_FILE = "data/faiss_index/indexed_hashes.txt"


def get_file_hash(path: str) -> Optional[str]:
    """
    Generate SHA256 hash of a file for deduplication.
    
    Args:
        path: Path to the file
    
    Returns:
        Hex digest of the file hash, or None if error
    """
    sha256_hash = hashlib.sha256()
    
    try:
        with open(path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error hashing file {path}: {e}")
        return None


def load_indexed_hashes() -> set[str]:
    """
    Load previously indexed document hashes.
    
    Returns:
        Set of indexed hash strings
    """
    hashes = set()
    
    if os.path.exists(INDEXED_HASHES_FILE):
        try:
            with open(INDEXED_HASHES_FILE, "r") as f:
                for line in f:
                    hashes.add(line.strip())
        except Exception as e:
            print(f"Error loading indexed hashes: {e}")
    
    return hashes


def save_indexed_hash(file_hash: str) -> None:
    """
    Save a document hash to prevent re-indexing.
    
    Args:
        file_hash: Hash of the indexed document
    """
    try:
        os.makedirs(os.path.dirname(INDEXED_HASHES_FILE), exist_ok=True)
        with open(INDEXED_HASHES_FILE, "a") as f:
            f.write(file_hash + "\n")
    except Exception as e:
        print(f"Error saving indexed hash: {e}")


def is_already_indexed(path: str) -> bool:
    """
    Check if a document has already been indexed.
    
    Args:
        path: Path to the PDF file
    
    Returns:
        True if already indexed, False otherwise
    """
    file_hash = get_file_hash(path)
    if not file_hash:
        return False
    
    indexed_hashes = load_indexed_hashes()
    return file_hash in indexed_hashes


def index_pdf(path: str, metadata: dict[str, Any], use_context: bool = True) -> bool:
    """
    Index a PDF document into the FAISS vector store.
    
    Args:
        path: Path to the PDF file
        metadata: Metadata dictionary with make, year, model, etc.
        use_context: Whether to prepend context to chunks for better retrieval
    
    Returns:
        True if indexing succeeded, False otherwise
    """
    # Check for deduplication
    if is_already_indexed(path):
        print(f"Already indexed: {path}")
        return False
    
    # Extract text from PDF
    print(f"Extracting text from: {path}")
    text = extract_text_from_pdf(path)
    
    if not text.strip():
        print(f"No text extracted from {path}, skipping...")
        return False
    
    # Chunk the text
    print(f"Chunking text ({len(text.split())} words)...")
    chunks = chunk_text(text)
    
    if not chunks:
        print(f"No chunks created from {path}, skipping...")
        return False
    
    # Add context to chunks for better retrieval (production-grade improvement)
    if use_context:
        contextual_chunks = []
        for chunk in chunks:
            contextual_chunks.append(create_contextual_chunk(chunk, metadata))
        chunks_to_embed = contextual_chunks
    else:
        chunks_to_embed = chunks
    
    # Generate embeddings
    print(f"Generating embeddings for {len(chunks_to_embed)} chunks...")
    try:
        vectors = embed_text(chunks_to_embed)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return False
    
    # Create metadata for each chunk
    metas = []
    for i, chunk in enumerate(chunks):
        chunk_meta = {
            "source": path,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "content": chunk,
            **metadata
        }
        
        # Add contextual version if used
        if use_context:
            chunk_meta["contextual_content"] = chunks_to_embed[i]
        
        metas.append(chunk_meta)
    
    # Add to vector store
    print(f"Adding {len(vectors)} vectors to FAISS index...")
    try:
        add_embeddings(vectors, metas)
        
        # Mark as indexed
        file_hash = get_file_hash(path)
        if file_hash:
            save_indexed_hash(file_hash)
        
        print(f"Successfully indexed: {path}")
        return True
        
    except Exception as e:
        print(f"Error adding to vector store: {e}")
        return False


def index_multiple_pdfs(
    paths: list[str],
    metadata_template: dict[str, Any],
    use_context: bool = True,
) -> dict[str, Any]:
    """
    Index multiple PDF files with shared metadata.
    
    Args:
        paths: List of PDF file paths
        metadata_template: Base metadata to apply to all PDFs
        use_context: Whether to prepend context to chunks
    
    Returns:
        Dictionary with indexing results
    """
    results = {
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    for path in paths:
        metadata = metadata_template.copy()
        
        # Add filename to metadata
        metadata["filename"] = os.path.basename(path)
        
        success = index_pdf(path, metadata, use_context)
        
        if success:
            results["success"] += 1
            results["details"].append({"path": path, "status": "success"})
        elif is_already_indexed(path):
            results["skipped"] += 1
            results["details"].append({"path": path, "status": "skipped"})
        else:
            results["failed"] += 1
            results["details"].append({"path": path, "status": "failed"})
    
    return results


def clear_index() -> None:
    """
    Clear all indexed documents and their hashes.
    Use with caution - this removes all indexed data.
    """
    import shutil
    
    # Remove FAISS index
    if os.path.exists("data/faiss_index/index.bin"):
        os.remove("data/faiss_index/index.bin")
    
    # Remove metadata
    if os.path.exists("data/faiss_index/meta.pkl"):
        os.remove("data/faiss_index/meta.pkl")
    
    # Remove hash tracking
    if os.path.exists(INDEXED_HASHES_FILE):
        os.remove(INDEXED_HASHES_FILE)
    
    print("Index cleared successfully")


if __name__ == "__main__":
    # Test indexing
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        
        metadata = {
            "make": "Honda",
            "year": "2016", 
            "model": "Accord",
            "source": pdf_path
        }
        
        success = index_pdf(pdf_path, metadata)
        print(f"Indexing {'succeeded' if success else 'failed'}")
    else:
        print("Usage: python indexer.py <pdf_path>")

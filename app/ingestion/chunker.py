"""
Text Chunker
Chunks text into smaller pieces for better retrieval.
Default chunk size is ~300 words.
"""
import re
from typing import List, Optional


def chunk_text(text: str, chunk_size: int = 300) -> List[str]:
    """
    Split text into chunks of approximately chunk_size words.
    
    Args:
        text: Input text to chunk
        chunk_size: Maximum number of words per chunk
    
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    
    return chunks


def chunk_text_with_overlap(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks for better context preservation.
    
    Args:
        text: Input text to chunk
        chunk_size: Maximum number of words per chunk
        overlap: Number of words to overlap between chunks
    
    Returns:
        List of text chunks with overlap
    """
    if not text or not text.strip():
        return []
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    words = text.split()
    chunks = []
    
    # Calculate step size (chunk_size - overlap)
    step = max(1, chunk_size - overlap)
    
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        
        # Stop if we've covered the entire text
        if i + chunk_size >= len(words):
            break
    
    return chunks


def _process_large_paragraph(para: str, max_words: int) -> List[str]:
    """
    Split a paragraph that exceeds max_words.
    
    Args:
        para: Paragraph text to split
        max_words: Maximum words per chunk
    
    Returns:
        List of sub-chunks from the paragraph
    """
    return chunk_text(para, max_words)


def _save_current_chunk(current_chunk: List[str], chunks: List[str]) -> None:
    """
    Helper to save accumulated chunk to chunks list.
    
    Args:
        current_chunk: List of paragraphs to join and save
        chunks: List receiving the saved chunk
    """
    if current_chunk:
        chunks.append(" ".join(current_chunk))


def _handle_paragraph_addition(
    para: str,
    para_word_count: int,
    current_chunk: List[str],
    current_word_count: int,
    max_words: int,
    min_words: int,
    chunks: List[str]
) -> tuple:
    """
    Determine how to add paragraph to chunk structure.
    
    Args:
        para: Cleaned paragraph text
        para_word_count: Word count of paragraph
        current_chunk: Currently accumulating chunk
        current_word_count: Words in current chunk
        max_words: Maximum words per chunk
        min_words: Minimum words per chunk
        chunks: List of finalized chunks
    
    Returns:
        Tuple of (new_current_chunk, new_word_count)
    """
    # If adding this paragraph would exceed max_words
    if current_word_count + para_word_count > max_words:
        # Save current chunk
        _save_current_chunk(current_chunk, chunks)
        
        # Start new chunk with this paragraph if it meets minimum size
        if para_word_count >= min_words:
            return [para], para_word_count
        else:
            return [], 0
    
    # Otherwise add to current chunk
    current_chunk.append(para)
    return current_chunk, current_word_count + para_word_count


def chunk_by_paragraphs(text: str, min_words: int = 50, max_words: int = 500) -> List[str]:
    """
    Split text by paragraphs, with min/max word limits.
    
    Args:
        text: Input text to chunk
        min_words: Minimum words per chunk (merge small paragraphs)
        max_words: Maximum words per chunk (split large paragraphs)
    
    Returns:
        List of text chunks grouped by paragraphs
    """
    if not text or not text.strip():
        return []
    
    # Split by double newlines (paragraphs)
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for paragraph in paragraphs:
        # Clean the paragraph
        para = re.sub(r'\s+', ' ', paragraph.strip())
        if not para:  # Skip empty paragraphs
            continue
            
        para_words = para.split()
        para_word_count = len(para_words)
        
        # If single paragraph is too large, split it
        if para_word_count > max_words:
            # First, save current accumulated chunk
            _save_current_chunk(current_chunk, chunks)
            current_chunk = []
            current_word_count = 0
            
            # Split large paragraph into sub-chunks
            sub_chunks = _process_large_paragraph(para, max_words)
            chunks.extend(sub_chunks)
        else:
            # Handle accumulation of regular-sized paragraphs
            current_chunk, current_word_count = _handle_paragraph_addition(
                para,
                para_word_count,
                current_chunk,
                current_word_count,
                max_words,
                min_words,
                chunks
            )
    
    # Don't forget the last chunk
    _save_current_chunk(current_chunk, chunks)
    
    return chunks


def create_contextual_chunk(chunk: str, metadata: dict) -> str:
    """
    Prepend context to chunk for better retrieval precision.
    
    Args:
        chunk: Text chunk
        metadata: Metadata including make, year, model, etc.
    
    Returns:
        Chunk with prepended context
    """
    context_parts = []
    
    # Build context string from metadata
    if metadata.get("make"):
        context_parts.append(f"[{metadata['make']}")
    if metadata.get("year"):
        context_parts.append(f"{metadata['year']}")
    if metadata.get("model"):
        context_parts.append(f"{metadata['model']} Service Manual]")
    elif metadata.get("source"):
        # Use filename as fallback
        filename = metadata["source"].split("/")[-1]
        context_parts.append(f"[{filename}]")
    
    # Add section info if available
    if metadata.get("section"):
        context_parts.append(f"Section: {metadata['section']}")
    
    context_prefix = " ".join(context_parts)
    
    if context_prefix:
        return f"{context_prefix}\n{chunk}"
    
    return chunk


if __name__ == "__main__":
    # Test chunking
    test_text = """
    This is a test document for chunking. It contains multiple sentences.
    The chunker should split this into smaller pieces of approximately 300 words each.
    Let's add more text to demonstrate the functionality.
    
    This is a new paragraph. It should be kept together with related content.
    The chunker has overlap functionality to preserve context between chunks.
    """ * 50  # Repeat to make it longer
    
    print(f"Original text length: {len(test_text.split())} words")
    
    chunks = chunk_text(test_text, chunk_size=50)
    print(f"\nCreated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i+1} ({len(chunk.split())} words):")
        print(chunk[:200] + "...")

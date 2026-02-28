"""
Type definitions for ShopMindAI.

Provides TypedDict definitions for structured data used throughout the application.
"""
from typing import Any, TypedDict


class ChunkDict(TypedDict):
    """Represents a text chunk with embeddings and metadata."""
    text: str
    embedding: list[float]
    chunk_index: int


class ManualMetadata(TypedDict):
    """Metadata about a diagnostic manual."""
    source: str
    title: str
    url: str
    file_path: str
    page_number: int | None
    chunk_index: int


class DocumentMetadata(TypedDict, total=False):
    """
    Metadata for processed documents.

    Using total=False allows optional fields.
    """
    pdf_path: str
    text_length: int
    num_chunks: int
    chunk_size: int
    chunk_overlap: int
    use_overlap: bool
    embedding_dimension: int


class SearchResult(TypedDict):
    """Result from vector store search."""
    id: str
    score: float
    metadata: ManualMetadata


class ProcessedDocument(TypedDict):
    """Result of document processing pipeline."""
    pdf_path: str
    text_extracted: int
    chunks: list[str]
    embeddings: list[list[float]]
    success: bool


class DiagnosticResult(TypedDict):
    """Diagnostic query result with scored documents."""
    query: str
    top_results: list[SearchResult]
    total_results: int
    retrieval_time_ms: float


class VINDecodeResult(TypedDict):
    """Result from VIN decoder service."""
    Results: list[dict[str, Any]]
    Count: int
    Message: str
    SearchCriteria: str


class WebSearchResult(TypedDict):
    """Result from web search."""
    title: str
    url: str
    snippet: str

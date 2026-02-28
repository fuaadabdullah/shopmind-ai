"""
Ingestion Module

Handles fetching, parsing, chunking, and indexing of vehicle manuals.

Core classes:
- IngestionManager: Main orchestrator
- DocumentProcessor: PDF processing pipeline
- CharmFetcher: Fetch from Operation CHARM
- ManualslibFetcher: Search ManualsLib
- IndexManager: FAISS indexing and deduplication
"""
from .document_processor import DocumentProcessor
from .fetchers import CharmFetcher, ManualslibFetcher
from .index_manager import IndexManager
from .ingestion_manager import IngestionManager

__all__ = [
    "IngestionManager",
    "DocumentProcessor",
    "CharmFetcher",
    "ManualslibFetcher",
    "IndexManager"
]


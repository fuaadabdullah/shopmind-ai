"""
Custom exception classes for ShopMindAI.

Provides domain-specific exceptions for better error handling and diagnostics.
"""
from typing import Optional


class ShopMindAIException(Exception):
    """Base exception for all ShopMindAI errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class EmbeddingError(ShopMindAIException):
    """Raised when embedding generation fails."""
    pass


class RetrievalError(ShopMindAIException):
    """Raised when document retrieval fails."""
    pass


class RankingError(ShopMindAIException):
    """Raised when diagnostic ranking fails."""
    pass


class VectorStoreError(ShopMindAIException):
    """Raised when vector store operations fail."""
    pass


class ProviderError(ShopMindAIException):
    """Raised when LLM provider requests fail."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when LLM provider request times out."""
    pass


class ProviderResponseError(ProviderError):
    """Raised when LLM provider returns invalid response."""
    pass


class ValidationError(ShopMindAIException):
    """Raised when input validation fails."""
    pass


class IngestionError(ShopMindAIException):
    """Raised when document ingestion fails."""
    pass

"""
Base provider interface and factory for LLM providers.

Provides abstraction for different LLM backends (GCP, SiliconeFlow, etc.).
Wraps providers with circuit breaker protection to prevent cascading failures.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)



class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All provider implementations must inherit from this class and implement
    the generate() method.
    """
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a completion for the given prompt.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated completion text
            
        Raises:
            ProviderError: If generation fails
        """
        pass


def get_provider() -> LLMProvider:
    """
    Get the configured LLM provider instance.
    
    Returns a circuit-breaker-wrapped provider if enabled.
    Providers are wrapped independently for separate failure tracking.
    
    Returns:
        Initialized provider based on DEFAULT_PROVIDER setting
        
    Raises:
        ValueError: If provider type is unknown
    """
    from .gcp_local import GCPProvider
    from .siliconeflow import SiliconeFlowProvider
    from .circuit_breaker import CircuitBreakerProvider
    
    if settings.DEFAULT_PROVIDER == "gcp":
        provider = GCPProvider()
        provider_name = "gcp"
    elif settings.DEFAULT_PROVIDER == "siliconeflow":
        provider = SiliconeFlowProvider()
        provider_name = "siliconeflow"
    else:
        raise ValueError(f"Unknown provider: {settings.DEFAULT_PROVIDER}")
    
    # Wrap with circuit breaker if enabled
    if settings.CIRCUIT_BREAKER_ENABLED:
        provider = CircuitBreakerProvider(
            provider=provider,
            provider_name=provider_name,
            failure_threshold=settings.CB_FAILURE_THRESHOLD,
            recovery_timeout=settings.CB_RECOVERY_TIMEOUT,
            success_threshold=settings.CB_SUCCESS_THRESHOLD,
        )
        logger.debug(f"Circuit breaker enabled for {provider_name} provider")
    
    return provider


def get_fallback_provider() -> LLMProvider | None:
    """
    Get the fallback LLM provider instance.
    
    Fallback provider is used when the primary provider circuit is open.
    By default, it's the opposite of DEFAULT_PROVIDER (gcp <-> siliconeflow).
    Can be overridden via LLM_FALLBACK_PROVIDER setting.
    
    Returns:
        Fallback provider instance or None if not available
    """
    from .gcp_local import GCPProvider
    from .siliconeflow import SiliconeFlowProvider
    from .circuit_breaker import CircuitBreakerProvider
    
    # Determine which provider to use as fallback
    if settings.LLM_FALLBACK_PROVIDER:
        fallback_provider_name = settings.LLM_FALLBACK_PROVIDER
    else:
        # Default: use opposite of primary provider
        fallback_provider_name = (
            "siliconeflow" if settings.DEFAULT_PROVIDER == "gcp" else "gcp"
        )
    
    try:
        if fallback_provider_name == "gcp":
            if not settings.GCP_MODEL_URL:
                logger.warning("GCP fallback provider not configured (no GCP_MODEL_URL)")
                return None
            provider = GCPProvider()
            provider_name = "gcp"
        elif fallback_provider_name == "siliconeflow":
            if not settings.SILICONEFLOW_API_KEY or not settings.SILICONEFLOW_URL:
                logger.warning("SiliconeFlow fallback provider not configured")
                return None
            provider = SiliconeFlowProvider()
            provider_name = "siliconeflow"
        else:
            logger.error(f"Unknown fallback provider: {fallback_provider_name}")
            return None
        
        # Wrap with circuit breaker if enabled
        if settings.CIRCUIT_BREAKER_ENABLED:
            provider = CircuitBreakerProvider(
                provider=provider,
                provider_name=provider_name,
                failure_threshold=settings.CB_FAILURE_THRESHOLD,
                recovery_timeout=settings.CB_RECOVERY_TIMEOUT,
                success_threshold=settings.CB_SUCCESS_THRESHOLD,
            )
            logger.debug(f"Circuit breaker enabled for {provider_name} fallback provider")
        
        return provider
    
    except Exception as e:
        logger.error(f"Error creating fallback provider: {str(e)}")
        return None


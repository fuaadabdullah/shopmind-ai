"""
Google Cloud Platform LLM provider implementation.
"""
import time
from typing import Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.logger import setup_logger
from app.exceptions import ProviderError, ProviderTimeoutError, ProviderResponseError
from .base import LLMProvider

logger = setup_logger(__name__)

# Timeout configuration (connect, read)
TIMEOUT = (5, 30)
MAX_RETRIES = 3


class GCPProvider(LLMProvider):
    """
    GCP-based LLM provider with retry logic and timeout handling.
    """
    
    def __init__(self):
        """Initialize GCP provider with session and retry strategy."""
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,  # 1s, 2s, 4s delays
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        if not settings.GCP_MODEL_URL:
            logger.warning("GCP_MODEL_URL not configured")
    
    def generate(self, prompt: str) -> str:
        """
        Generate completion using GCP model endpoint.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated response text
            
        Raises:
            ProviderError: If request fails
            ProviderTimeoutError: If request times out
            ProviderResponseError: If response is invalid
        """
        if not settings.GCP_MODEL_URL:
            raise ProviderError(
                "GCP_MODEL_URL not configured",
                details={"provider": "gcp"}
            )
        
        try:
            logger.debug(f"Sending request to GCP model: {settings.GCP_MODEL_URL}")
            start_time = time.time()
            
            response = self.session.post(
                settings.GCP_MODEL_URL,
                json={"prompt": prompt},
                timeout=TIMEOUT
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"GCP request completed in {duration_ms}ms")
            
            # Check response status
            if not response.ok:
                logger.error(
                    f"GCP request failed with status {response.status_code}: "
                    f"{response.text[:200]}"
                )
                raise ProviderResponseError(
                    f"GCP request failed: {response.status_code}",
                    details={
                        "status_code": response.status_code,
                        "response": response.text[:500]
                    }
                )
            
            # Parse response
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse GCP response as JSON: {str(e)}")
                raise ProviderResponseError(
                    "Invalid JSON response from GCP",
                    details={"error": str(e), "response": response.text[:200]}
                )
            
            # Extract response text
            if "response" not in data:
                logger.error(f"Missing 'response' field in GCP response: {data}")
                raise ProviderResponseError(
                    "Missing 'response' field in GCP response",
                    details={"data": data}
                )
            
            result = data["response"]
            logger.debug(f"GCP response length: {len(result)} characters")
            return result
            
        except requests.exceptions.Timeout as e:
            logger.error(f"GCP request timed out: {str(e)}")
            raise ProviderTimeoutError(
                "GCP request timed out",
                details={"timeout": TIMEOUT, "error": str(e)}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"GCP request failed: {str(e)}", exc_info=True)
            raise ProviderError(
                "GCP request failed",
                details={"error": str(e)}
            )
        except (ProviderError, ProviderTimeoutError, ProviderResponseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in GCP provider: {str(e)}", exc_info=True)
            raise ProviderError(
                "Unexpected error in GCP provider",
                details={"error": str(e)}
            )

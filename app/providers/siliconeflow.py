"""
SiliconeFlow LLM provider implementation.
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


class SiliconeFlowProvider(LLMProvider):
    """
    SiliconeFlow LLM provider with retry logic and timeout handling.
    """
    
    def __init__(self):
        """Initialize SiliconeFlow provider with session and retry strategy."""
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
        
        if not settings.SILICONEFLOW_API_KEY:
            logger.warning("SILICONEFLOW_API_KEY not configured")
        if not settings.SILICONEFLOW_URL:
            logger.warning("SILICONEFLOW_URL not configured")
    
    def generate(self, prompt: str) -> str:
        """
        Generate completion using SiliconeFlow API.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated response text
            
        Raises:
            ProviderError: If request fails
            ProviderTimeoutError: If request times out
            ProviderResponseError: If response is invalid
        """
        if not settings.SILICONEFLOW_URL:
            raise ProviderError(
                "SILICONEFLOW_URL not configured",
                details={"provider": "siliconeflow"}
            )
        
        if not settings.SILICONEFLOW_API_KEY:
            raise ProviderError(
                "SILICONEFLOW_API_KEY not configured",
                details={"provider": "siliconeflow"}
            )
        
        try:
            logger.debug(f"Sending request to SiliconeFlow: {settings.SILICONEFLOW_URL}")
            start_time = time.time()
            
            headers = {
                "Authorization": f"Bearer {settings.SILICONEFLOW_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = self.session.post(
                settings.SILICONEFLOW_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"SiliconeFlow request completed in {duration_ms}ms")
            
            # Check response status
            if not response.ok:
                logger.error(
                    f"SiliconeFlow request failed with status {response.status_code}: "
                    f"{response.text[:200]}"
                )
                raise ProviderResponseError(
                    f"SiliconeFlow request failed: {response.status_code}",
                    details={
                        "status_code": response.status_code,
                        "response": response.text[:500]
                    }
                )
            
            # Parse response
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse SiliconeFlow response as JSON: {str(e)}")
                raise ProviderResponseError(
                    "Invalid JSON response from SiliconeFlow",
                    details={"error": str(e), "response": response.text[:200]}
                )
            
            # Extract response text
            try:
                result = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected SiliconeFlow response structure: {data}")
                raise ProviderResponseError(
                    "Unexpected response structure from SiliconeFlow",
                    details={"error": str(e), "data": data}
                )
            
            logger.debug(f"SiliconeFlow response length: {len(result)} characters")
            return result
            
        except requests.exceptions.Timeout as e:
            logger.error(f"SiliconeFlow request timed out: {str(e)}")
            raise ProviderTimeoutError(
                "SiliconeFlow request timed out",
                details={"timeout": TIMEOUT, "error": str(e)}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"SiliconeFlow request failed: {str(e)}", exc_info=True)
            raise ProviderError(
                "SiliconeFlow request failed",
                details={"error": str(e)}
            )
        except (ProviderError, ProviderTimeoutError, ProviderResponseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in SiliconeFlow provider: {str(e)}", exc_info=True)
            raise ProviderError(
                "Unexpected error in SiliconeFlow provider",
                details={"error": str(e)}
            )

"""
Application configuration management.

Loads configuration from environment variables with validation and defaults.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """
    Application settings loaded from environment variables.
    
    Environment Variables:
        GCP_MODEL_URL: URL for GCP model endpoint
        SILICONEFLOW_API_KEY: API key for SiliconeFlow provider
        SILICONEFLOW_URL: URL for SiliconeFlow API
        DEFAULT_PROVIDER: LLM provider to use ("gcp" or "siliconeflow", default: "gcp")
        ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins (default: "*")
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, default: "INFO")
    """
    
    # LLM Provider Configuration
    GCP_MODEL_URL: Optional[str] = os.getenv("GCP_MODEL_URL")
    SILICONEFLOW_API_KEY: Optional[str] = os.getenv("SILICONEFLOW_API_KEY")
    SILICONEFLOW_URL: Optional[str] = os.getenv("SILICONEFLOW_URL")
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "gcp")
    
    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_ENABLED: bool = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
    CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
    CB_RECOVERY_TIMEOUT: int = int(os.getenv("CB_RECOVERY_TIMEOUT", "30"))
    CB_SUCCESS_THRESHOLD: int = int(os.getenv("CB_SUCCESS_THRESHOLD", "2"))
    
    # LLM Fallback Provider (opposite of DEFAULT_PROVIDER if not specified)
    LLM_FALLBACK_PROVIDER: Optional[str] = os.getenv("LLM_FALLBACK_PROVIDER")
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Vector Store Configuration
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "data/faiss_index")
    
    # Embedding Model Configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    
    # Application Configuration
    MAX_RETRIEVE_DOCS: int = int(os.getenv("MAX_RETRIEVE_DOCS", "10"))
    
    def validate(self) -> None:
        """
        Validate configuration and log warnings for missing values.
        
        Raises:
            ValueError: If critical configuration is invalid
        """
        if self.DEFAULT_PROVIDER not in ["gcp", "siliconeflow"]:
            raise ValueError(
                f"Invalid DEFAULT_PROVIDER: {self.DEFAULT_PROVIDER}. "
                f"Must be 'gcp' or 'siliconeflow'"
            )
        
        if self.DEFAULT_PROVIDER == "gcp" and not self.GCP_MODEL_URL:
            raise ValueError("GCP_MODEL_URL must be set when using GCP provider")
        
        if self.DEFAULT_PROVIDER == "siliconeflow":
            if not self.SILICONEFLOW_API_KEY:
                raise ValueError(
                    "SILICONEFLOW_API_KEY must be set when using SiliconeFlow provider"
                )
            if not self.SILICONEFLOW_URL:
                raise ValueError(
                    "SILICONEFLOW_URL must be set when using SiliconeFlow provider"
                )


# Global settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
except ValueError as e:
    # Log warning but don't crash on import
    import sys
    print(f"Configuration warning: {str(e)}", file=sys.stderr)

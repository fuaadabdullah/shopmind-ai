"""Factory function for creating and configuring the FastAPI application."""
import os
import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .exceptions import (
    ShopMindAIException,
    EmbeddingError,
    ProviderError,
    ProviderTimeoutError,
    RankingError,
    RetrievalError,
    ValidationError as AppValidationError
)
from .logger import setup_logger

logger = setup_logger(__name__)


def create_app() -> tuple[FastAPI, Limiter]:
    """
    Create and configure the FastAPI application.

    Returns:
        Tuple of (FastAPI app instance, Limiter instance)
    """
    # Get allowed origins from environment (comma-separated)
    allowed_origins: list[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if allowed_origins == ["*"]:
        logger.warning(
            "CORS configured to allow all origins (*). "
            "Set ALLOWED_ORIGINS environment variable for production."
        )

    # Rate limiter configuration
    limiter: Limiter = Limiter(key_func=get_remote_address)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan events."""
        logger.info("ShopMindAI application starting up")
        
        # Initialize database schema using Alembic migrations
        try:
            from .database import init_db
            init_db()
            logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise
        
        # Warm up embedding model
        try:
            from .embeddings import _get_model
            _get_model()
            logger.info("Embedding model preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload embedding model: {str(e)}")

        yield

        logger.info("ShopMindAI application shutting down")

    # Create FastAPI app instance
    app: FastAPI = FastAPI(
        title="ShopMindAI",
        description="AI-powered automotive diagnostic assistance",
        version="1.0.0",
        lifespan=lifespan
    )

    # Configure rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        max_age=3600,
    )

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Add unique request ID for tracing."""
        request_id: str = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time: float = time.time()

        # Add request ID to log context
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"request_id": request_id}
        )

        response: Response = await call_next(request)

        duration_ms: int = int((time.time() - start_time) * 1000)
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"[{response.status_code}] in {duration_ms}ms",
            extra={"request_id": request_id, "duration_ms": duration_ms}
        )

        response.headers["X-Request-ID"] = request_id
        return response

    # Add exception handlers
    @app.exception_handler(ShopMindAIException)
    async def shopmindai_exception_handler(
        request: Request, exc: ShopMindAIException
    ) -> JSONResponse:
        """Handle application-specific exceptions."""
        request_id: str = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"Application error: {exc.message}",
            extra={"request_id": request_id, "details": exc.details},
            exc_info=True
        )

        # Map exception types to HTTP status codes
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(exc, AppValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, ProviderTimeoutError):
            status_code = status.HTTP_504_GATEWAY_TIMEOUT
        elif isinstance(
            exc,
            (EmbeddingError, RetrievalError, RankingError, ProviderError)
        ):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.message,
                "details": exc.details,
                "request_id": request_id
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        request_id: str = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={"request_id": request_id},
            exc_info=True
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request_id": request_id
            }
        )

    return app, limiter

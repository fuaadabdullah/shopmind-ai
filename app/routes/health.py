"""
Health check endpoint for monitoring and load balancers.
"""
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check endpoint"
)
async def health_check(request: Request) -> dict[str, str]:
    """
    Health check endpoint for monitoring and load balancers.

    Returns basic health status of the application.
    """
    return {
        "status": "healthy",
        "service": "ShopMindAI",
        "version": "1.0.0"
    }

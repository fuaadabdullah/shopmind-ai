"""
API route modules for ShopMindAI.
"""
from .admin import router as admin_router
from .diagnose import router as diagnose_router
from .feedback import router as feedback_router
from .health import router as health_router
from .metrics import router as metrics_router

__all__ = ["health_router", "diagnose_router", "admin_router", "feedback_router", "metrics_router"]

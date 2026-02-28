"""
ShopMindAI FastAPI application.

Provides diagnostic assistance for automotive repair by combining semantic search
over repair manuals with LLM-based reasoning. Integrates Torch-based predictions
as an optional v2 intelligence layer.
"""
from fastapi.staticfiles import StaticFiles

from .app_factory import create_app
from .logger import setup_logger
from .routes import admin_router, diagnose_router, feedback_router, health_router, metrics_router

logger = setup_logger(__name__)

# Create and configure the FastAPI application
app, limiter = create_app()

# Register routers with the app
app.include_router(metrics_router)
app.include_router(health_router)
app.include_router(diagnose_router)
app.include_router(feedback_router)
app.include_router(admin_router)

# Mount static files AFTER API routes to avoid conflicts
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

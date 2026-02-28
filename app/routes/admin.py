"""
Admin endpoints for system management and operations.

Future admin operations will include:
- Ingestion status and controls
- Model reloading
- System health diagnostics
- Configuration updates
"""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


# Placeholder for future admin endpoints

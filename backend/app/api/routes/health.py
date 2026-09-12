from typing import Any

from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "airspace-intelligence",
        "version": "0.1.0",
    }

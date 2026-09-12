from fastapi import APIRouter

from app.api.routes import health, aircraft

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(aircraft.router, prefix="/aircraft", tags=["aircraft"])

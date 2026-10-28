"""GET /health — no auth required."""
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}

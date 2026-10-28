"""GET /me — current user info."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.config import get_settings
from app.db import User, Organization, get_db_session

router = APIRouter(tags=["identity"])


@router.get("/me")
async def get_me(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    user = await session.get(User, principal.user_id)
    org = await session.get(Organization, principal.org_id)
    return {
        "user": {
            "id": str(principal.user_id),
            "email": user.email if user else "unknown",
            "role": user.role if user else "member",
        },
        "org": {
            "id": str(principal.org_id),
            "name": org.name if org else "Unknown",
        },
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "audits_per_hour": settings.audits_per_hour_per_org,
        },
    }

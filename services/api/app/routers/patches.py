"""
Patches endpoints (Milestone 5) — stubbed until feature flag 'patches' enabled.
Table exists; endpoints return 422 until enabled.
"""
from fastapi import APIRouter, Depends
from app.auth import get_principal
from app.errors import feature_not_enabled
import uuid

router = APIRouter(tags=["patches"])


@router.post("/audits/{audit_id}/findings/{finding_id}/patches", status_code=202)
async def generate_patch(audit_id: uuid.UUID, finding_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("patches")


@router.get("/audits/{audit_id}/findings/{finding_id}/patches")
async def list_patches(audit_id: uuid.UUID, finding_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("patches")


@router.get("/patches/{patch_id}")
async def get_patch(patch_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("patches")


@router.post("/patches/{patch_id}/verify", status_code=202)
async def verify_patch(patch_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("patches")

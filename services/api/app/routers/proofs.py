"""
Proofs endpoints (Milestone 6) — stubbed until feature flag 'proofs' enabled.
"""
from fastapi import APIRouter, Depends
from app.auth import get_principal
from app.errors import feature_not_enabled
import uuid

router = APIRouter(tags=["proofs"])


@router.post("/audits/{audit_id}/findings/{finding_id}/proof", status_code=202)
async def generate_proof(audit_id: uuid.UUID, finding_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("proofs")


@router.get("/findings/{finding_id}/proof")
async def get_proof(finding_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("proofs")

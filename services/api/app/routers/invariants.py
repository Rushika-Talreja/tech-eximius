"""
Invariants endpoints (Milestone 7) — stubbed until feature flag 'invariants' enabled.
"""
from fastapi import APIRouter, Depends
from app.auth import get_principal
from app.errors import feature_not_enabled
import uuid

router = APIRouter(tags=["invariants"])


@router.post("/audits/{audit_id}/invariant-runs", status_code=202)
async def start_invariant_run(audit_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("invariants")


@router.get("/audits/{audit_id}/invariant-runs")
async def list_invariant_runs(audit_id: uuid.UUID, principal=Depends(get_principal)):
    raise feature_not_enabled("invariants")

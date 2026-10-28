"""
Projects endpoints.
POST   /projects
GET    /projects
GET    /projects/{project_id}
DELETE /projects/{project_id}  — soft delete
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, RequireWrite, get_principal
from app.db import Audit, Project, get_db_session
from app.errors import not_found

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


def _format_project(p: Project, audit_count: int = 0, latest_audit: Audit | None = None) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at.isoformat(),
        "audit_count": audit_count,
        "latest_audit": (
            {
                "id": str(latest_audit.id),
                "status": latest_audit.status,
                "created_at": latest_audit.created_at.isoformat(),
            }
            if latest_audit
            else None
        ),
    }


@router.post("/projects", status_code=201)
async def create_project(
    body: CreateProjectRequest,
    principal: Principal = RequireWrite,
    session: AsyncSession = Depends(get_db_session),
):
    project = Project(
        org_id=principal.org_id,
        name=body.name,
        description=body.description,
        created_by=principal.user_id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return _format_project(project)


@router.get("/projects")
async def list_projects(
    limit: int = Query(default=25, le=100),
    cursor: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Project)
        .where(Project.org_id == principal.org_id, Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
        .limit(limit + 1)
    )
    if cursor:
        # Simple cursor: created_at ISO
        try:
            dt = datetime.fromisoformat(cursor)
            query = query.where(Project.created_at < dt)
        except ValueError:
            pass

    result = await session.execute(query)
    projects = result.scalars().all()
    has_more = len(projects) > limit
    projects = projects[:limit]

    items = []
    for p in projects:
        count_result = await session.execute(
            select(func.count(Audit.id)).where(Audit.project_id == p.id)
        )
        count = count_result.scalar() or 0
        latest_result = await session.execute(
            select(Audit)
            .where(Audit.project_id == p.id)
            .order_by(Audit.created_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        items.append(_format_project(p, count, latest))

    return {
        "items": items,
        "next_cursor": projects[-1].created_at.isoformat() if has_more and projects else None,
    }


@router.get("/projects/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    project = await session.get(Project, project_id)
    if not project or project.org_id != principal.org_id or project.deleted_at:
        raise not_found("Project", str(project_id))

    count_result = await session.execute(
        select(func.count(Audit.id)).where(Audit.project_id == project_id)
    )
    count = count_result.scalar() or 0
    latest_result = await session.execute(
        select(Audit)
        .where(Audit.project_id == project_id)
        .order_by(Audit.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    return _format_project(project, count, latest)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
):
    project = await session.get(Project, project_id)
    if not project or project.org_id != principal.org_id or project.deleted_at:
        raise not_found("Project", str(project_id))
    project.deleted_at = datetime.utcnow()
    await session.commit()

"""
Arq Worker for DeFi Contract Auditor.
Executes audit pipeline stages and writes events to Postgres.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Audit, AuditEvent, AuditFile, PrivilegeResult, RoleDeclaration, Upload, get_session_factory
from app.logging_config import configure_logging, get_logger
from app.storage import get_storage_client
from auditor_core.detectors.scanner import build_coverage_statement, run_scanning_stage
from auditor_core.pipeline.building import BuildFailedError, run_building_stage
from auditor_core.privilege_map.analyzer import run_analyzing_stage, run_privilege_map_stage
from auditor_core.scoring.heuristic import compute_heuristic_scores
from sqlalchemy import select

logger = get_logger(__name__)


async def emit_event(
    session: AsyncSession,
    audit_id: uuid.UUID,
    org_id: uuid.UUID,
    stage: str | None,
    level: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    event = AuditEvent(
        audit_id=audit_id,
        org_id=org_id,
        stage=stage,
        level=level,
        message=message,
        data=data or {},
    )
    session.add(event)
    await session.commit()


async def run_audit_pipeline(
    ctx: dict[str, Any],
    audit_id_str: str,
    org_id_str: str,
    options: dict[str, Any],
    role_declarations: list[dict[str, Any]],
) -> None:
    audit_id = uuid.UUID(audit_id_str)
    org_id = uuid.UUID(org_id_str)
    session_factory = get_session_factory()
    settings = get_settings()

    logger.info("audit_pipeline_started", audit_id=audit_id_str, org_id=org_id_str)

    async with session_factory() as session:
        if not settings.database_url.startswith("sqlite"):
            await session.execute(text(f"SET LOCAL app.org_id = '{org_id}'"))

        audit = await session.get(Audit, audit_id)
        if not audit:
            logger.error("audit_not_found", audit_id=audit_id_str)
            return

        audit.status = "running"
        audit.started_at = datetime.utcnow()
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            None,
            "info",
            "Pipeline started",
            {"status": "running", "event_type": "log"},
        )

        # ─── Stage 1: Building ────────────────────────────────────────────────
        audit.stage = "building"
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "building",
            "info",
            "Starting stage building",
            {"event_type": "stage_started"},
        )

        upload = await session.get(Upload, audit.upload_id)
        if not upload:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "NOT_FOUND", "message": "Upload not found", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "building",
                "error",
                "Upload artifact not found",
                {"event_type": "audit_failed"},
            )
            return

        storage = get_storage_client()
        try:
            upload_bytes = storage.get_object(upload.object_key)
        except Exception as exc:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "INTERNAL", "message": f"Storage retrieval failed: {exc}", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "building",
                "error",
                "Could not retrieve upload payload",
                {"event_type": "audit_failed"},
            )
            return

        try:
            building_result = run_building_stage(
                upload_bytes=upload_bytes,
                kind=upload.kind,
                options=options or audit.options or {},
                org_id=str(org_id),
                audit_id=str(audit_id),
                storage_client=storage,
            )
        except BuildFailedError as bfe:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {
                "code": "BUILD_FAILED",
                "message": bfe.message,
                "details": {"diagnostics": bfe.diagnostics},
            }
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "building",
                "error",
                "Build failed: compilation errors",
                {
                    "event_type": "audit_failed",
                    "error": "BUILD_FAILED",
                    "diagnostics": bfe.diagnostics,
                },
            )
            logger.info("audit_build_failed", audit_id=audit_id_str, errors_count=len(bfe.diagnostics))
            return
        except Exception as exc:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "INTERNAL", "message": f"Unexpected building failure: {exc}", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "building",
                "error",
                f"Building error: {exc}",
                {"event_type": "audit_failed"},
            )
            logger.exception("audit_building_exception", audit_id=audit_id_str)
            return

        # Store audit_files rows
        for file_row in building_result.audit_files:
            audit_file = AuditFile(
                id=file_row["id"],
                audit_id=audit_id,
                org_id=org_id,
                path=file_row["path"],
                sha256=file_row["sha256"],
                line_count=file_row["line_count"],
                is_dependency=file_row["is_dependency"],
                object_key=file_row["object_key"],
            )
            session.add(audit_file)

        audit.source_manifest = building_result.source_manifest
        audit.compiler_version = building_result.solc_version
        audit.toolchain = building_result.toolchain
        audit.coverage = {
            "analyzed": {
                "files": building_result.analyzed_files,
                "contracts": list(building_result.contracts.keys()),
            },
            "not_analyzed": building_result.not_analyzed_files,
            "out_of_scope": [
                "Economic design and tokenomics",
                "Oracle trust assumptions",
                "Governance attack economics",
                "Off-chain components and infrastructure",
                "Deployment configuration (constructor args, initial roles)",
            ],
        }
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "building",
            "info",
            f"Building stage complete. Compiled {len(building_result.analyzed_files)} files.",
            {
                "event_type": "stage_completed",
                "files_count": len(building_result.source_manifest),
                "solc_version": building_result.solc_version,
            },
        )

        # Check for cancellation
        await session.refresh(audit)
        if audit.cancel_requested:
            audit.status = "cancelled"
            audit.finished_at = datetime.utcnow()
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "building",
                "warn",
                "Audit cancelled by user",
                {"status": "cancelled", "event_type": "log"},
            )
            return

        # Store initial role declarations if provided
        for decl in role_declarations:
            r_key = decl.get("role_key")
            if r_key:
                h_type = decl.get("holder_type", "eoa")
                params = {k: v for k, v in decl.items() if k not in ("role_key", "holder_type") and v is not None}
                session.add(RoleDeclaration(
                    audit_id=audit_id,
                    org_id=org_id,
                    role_key=r_key,
                    holder_type=h_type,
                    params=params,
                ))
        await session.flush()

        # Reconstruct sources dictionary from audit_files in storage
        sources: dict[str, str] = {}
        for file_row in building_result.audit_files:
            try:
                data_bytes = storage.get_object(file_row["object_key"])
                sources[file_row["path"]] = data_bytes.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("failed_to_fetch_file_content", path=file_row["path"], error=str(exc))

        # ─── Stage 2: Analyzing ───────────────────────────────────────────────
        audit.stage = "analyzing"
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "analyzing",
            "info",
            "Starting stage analyzing",
            {"event_type": "stage_started"},
        )

        start_time_an = time.perf_counter()
        try:
            models, contract_db_ids, not_analyzed_slither = await run_analyzing_stage(
                audit_id=audit_id,
                org_id=org_id,
                session=session,
                sources=sources,
                solc_version=building_result.solc_version,
            )
        except Exception as exc:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "INTERNAL", "message": f"Analyzing stage failed: {exc}", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "analyzing",
                "error",
                f"Analyzing error: {exc}",
                {"event_type": "audit_failed"},
            )
            return

        if not_analyzed_slither:
            cov = dict(audit.coverage or {})
            existing_not_an = cov.get("not_analyzed", [])
            existing_not_an.extend(not_analyzed_slither)
            cov["not_analyzed"] = existing_not_an
            audit.coverage = cov
            await session.commit()

        duration_an = int((time.perf_counter() - start_time_an) * 1000)
        await emit_event(
            session,
            audit_id,
            org_id,
            "analyzing",
            "info",
            f"Analyzing stage complete. Extracted {len(models)} contracts.",
            {"event_type": "stage_completed", "duration_ms": duration_an, "contracts_count": len(models)},
        )

        # Check for cancellation
        await session.refresh(audit)
        if audit.cancel_requested:
            audit.status = "cancelled"
            audit.finished_at = datetime.utcnow()
            await session.commit()
            return

        # ─── Stage 3: Privilege Map ───────────────────────────────────────────
        audit.stage = "privilege_map"
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "privilege_map",
            "info",
            "Starting stage privilege_map",
            {"event_type": "stage_started"},
        )

        start_time_pm = time.perf_counter()
        try:
            pmap_result = await run_privilege_map_stage(
                audit_id=audit_id,
                org_id=org_id,
                session=session,
                contracts=models,
                contract_db_ids=contract_db_ids,
            )
        except Exception as exc:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "INTERNAL", "message": f"Privilege map stage failed: {exc}", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "privilege_map",
                "error",
                f"Privilege map error: {exc}",
                {"event_type": "audit_failed"},
            )
            return

        # Emit privilege_map_ready event per requirement 8!
        await emit_event(
            session,
            audit_id,
            org_id,
            "privilege_map",
            "info",
            "Privilege map ready",
            {
                "event_type": "privilege_map_ready",
                "roles_count": len(pmap_result.get("roles", [])),
                "actions_count": pmap_result.get("actions_count", 0),
            },
        )

        duration_pm = int((time.perf_counter() - start_time_pm) * 1000)
        await emit_event(
            session,
            audit_id,
            org_id,
            "privilege_map",
            "info",
            f"Privilege map stage complete. {len(pmap_result.get('roles', []))} roles analyzed.",
            {"event_type": "stage_completed", "duration_ms": duration_pm},
        )

        # Check for cancellation
        await session.refresh(audit)
        if audit.cancel_requested:
            audit.status = "cancelled"
            audit.finished_at = datetime.utcnow()
            await session.commit()
            return

        # ─── Stage 4: Scanning ────────────────────────────────────────────────
        audit.stage = "scanning"
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "scanning",
            "info",
            "Starting stage scanning",
            {"event_type": "stage_started"},
        )

        start_time_scan = time.perf_counter()
        try:
            candidates = await run_scanning_stage(
                audit_id=audit_id,
                org_id=org_id,
                session=session,
                sources=sources,
                solc_version=building_result.solc_version,
                models=models,
                missing_ac=pmap_result.get("missing_access_control", []),
                privilege_candidates=pmap_result.get("candidates", []),
                options=options or audit.options or {},
            )
            for c in candidates:
                await emit_event(
                    session,
                    audit_id,
                    org_id,
                    "scanning",
                    "info",
                    f"Finding detected: {c.title}",
                    {
                        "event_type": "finding_added",
                        "finding_id": str(c.id),
                        "severity": c.severity,
                        "title": c.title,
                        "source": c.source,
                    },
                )
        except Exception as exc:
            audit.status = "failed"
            audit.finished_at = datetime.utcnow()
            audit.error = {"code": "INTERNAL", "message": f"Scanning stage failed: {exc}", "details": {}}
            await session.commit()
            await emit_event(
                session,
                audit_id,
                org_id,
                "scanning",
                "error",
                f"Scanning stage failed: {exc}",
                {"error": str(exc), "event_type": "stage_failed"},
            )
            await emit_event(
                session,
                audit_id,
                org_id,
                None,
                "error",
                "Pipeline execution failed",
                {"event_type": "audit_failed"},
            )
            return

        duration_scan = int((time.perf_counter() - start_time_scan) * 1000)
        await emit_event(
            session,
            audit_id,
            org_id,
            "scanning",
            "info",
            f"Scanning stage complete. Found {len(candidates)} findings.",
            {"event_type": "stage_completed", "duration_ms": duration_scan, "findings_count": len(candidates)},
        )

        # Check for cancellation
        await session.refresh(audit)
        if audit.cancel_requested:
            audit.status = "cancelled"
            audit.finished_at = datetime.utcnow()
            await session.commit()
            return

        # ─── Stage 11: Reporting ──────────────────────────────────────────────
        audit.stage = "reporting"
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            "reporting",
            "info",
            "Starting stage reporting",
            {"event_type": "stage_started"},
        )

        start_time_rep = time.perf_counter()

        # Build coverage statement
        all_not_analyzed = (
            building_result.not_analyzed_files
            + not_analyzed_slither
            + [{"reason": str(n)} if isinstance(n, str) else n for n in pmap_result.get("undetected_notes", [])]
        )
        cov_stmt = build_coverage_statement(
            file_paths=list(sources.keys()),
            contract_names=list(models.keys()),
            not_analyzed_items=all_not_analyzed,
        )
        audit.coverage = cov_stmt

        # Load privilege results for heuristic scoring
        priv_results = (await session.execute(
            select(PrivilegeResult).where(PrivilegeResult.audit_id == audit_id)
        )).scalars().all()

        scores_data = compute_heuristic_scores(candidates, privilege_results=priv_results)
        audit.scores = scores_data
        audit.counts = scores_data.get("counts", {})

        duration_rep = int((time.perf_counter() - start_time_rep) * 1000)
        await emit_event(
            session,
            audit_id,
            org_id,
            "reporting",
            "info",
            "Reporting stage complete.",
            {"event_type": "stage_completed", "duration_ms": duration_rep},
        )

        # Pipeline completed
        audit.status = "complete"
        audit.stage = "reporting"
        audit.finished_at = datetime.utcnow()
        await session.commit()

        await emit_event(
            session,
            audit_id,
            org_id,
            None,
            "info",
            "Pipeline completed successfully",
            {"status": "complete", "event_type": "audit_completed"},
        )
        logger.info("audit_pipeline_complete", audit_id=audit_id_str)


class WorkerSettings:
    functions = [run_audit_pipeline]
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url) if settings.redis_url else None
    max_jobs = 4
    poll_delay = 0.5


if __name__ == "__main__":
    from arq import run_worker

    configure_logging()
    logger.info("arq_worker_starting")
    run_worker(WorkerSettings)  # type: ignore[arg-type]

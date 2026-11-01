"""
High-level patch orchestration for Milestone 5.
Coordinates PatchPlanner and PatchVerifier with:
- Up to 3 attempts with failure log feedback
- Guidance fallback when verification fails
- FALLBACK MODE: PATCH_MODE=suggest_only returns unverified diffs without claiming compilation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.logging_config import get_logger

from auditor_core.patching.planner import plan_patch, render_unified_diff
from auditor_core.patching.verifier import VerificationResult, verify_patch

logger = get_logger(__name__)


async def generate_and_verify_patch(
    sources: dict[str, str],
    target_finding: dict[str, Any],
    original_findings: list[dict[str, Any]] | list[Any],
    solc_version: str = "0.8.24",
    remediation_text: str = "",
    patch_mode: str = "verify",
    max_attempts: int = 3,
) -> dict[str, Any]:
    """
    Main entrypoint for generating and verifying a patch.
    """
    target_file = target_finding.get("file_path") or target_finding.get("file") or ""
    # Find matching source content
    matched_key = None
    if target_file in sources:
        matched_key = target_file
    else:
        for k in sources:
            if k == target_file or Path(k).name == Path(target_file).name or k.endswith("/" + target_file):
                matched_key = k
                break

    if not matched_key:
        matched_key = list(sources.keys())[0] if sources else "Contract.sol"

    original_file_content = sources.get(matched_key, "")

    # ─── FALLBACK MODE: suggest_only ──────────────────────────────────────────
    if patch_mode == "suggest_only":
        try:
            plan = await plan_patch(
                finding=target_finding,
                file_content=original_file_content,
                remediation_text=remediation_text,
            )
            _, diff = render_unified_diff(original_file_content, plan.hunks, matched_key)
            return {
                "status": "unverified",
                "unified_diff": diff,
                "rationale": plan.rationale,
                "compiles": None,
                "finding_cleared": None,
                "new_findings": [],
                "gas_delta": {},
                "verification_log": [
                    {
                        "step": "fallback_mode",
                        "ok": True,
                        "message": "PATCH_MODE=suggest_only: returned unverified diff without compilation claims",
                    }
                ],
            }
        except Exception as exc:
            return {
                "status": "unverified",
                "unified_diff": "",
                "rationale": f"Suggest-only patch generation failed: {exc}",
                "compiles": None,
                "finding_cleared": None,
                "new_findings": [],
                "gas_delta": {},
                "verification_log": [{"step": "plan", "ok": False, "message": str(exc)}],
            }

    # ─── Standard Mode: Verification in Scratch Copy ─────────────────────────
    failure_log: str | None = None
    last_log: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        logger.info("patch_generation_attempt", attempt=attempt, finding=target_finding.get("title"))
        try:
            plan = await plan_patch(
                finding=target_finding,
                file_content=original_file_content,
                remediation_text=remediation_text,
                previous_failure_log=failure_log,
            )

            if not plan.hunks:
                failure_log = "Planner returned empty hunks"
                last_log.append({"step": "plan", "ok": False, "attempt": attempt, "message": failure_log})
                continue

            _, diff = render_unified_diff(original_file_content, plan.hunks, matched_key)

            v_res: VerificationResult = await verify_patch(
                project_sources=sources,
                unified_diff=diff,
                target_finding=target_finding,
                original_findings=original_findings,
                solc_version=solc_version,
            )

            last_log = v_res.log

            if v_res.ok:
                return {
                    "status": "verified",
                    "unified_diff": diff,
                    "rationale": plan.rationale,
                    "compiles": v_res.compiles,
                    "finding_cleared": v_res.finding_cleared,
                    "new_findings": v_res.new_findings,
                    "gas_delta": v_res.gas_delta,
                    "verification_log": v_res.log,
                }
            else:
                failure_log = v_res.failure_summary

        except Exception as exc:
            failure_log = str(exc)
            last_log.append({"step": "error", "attempt": attempt, "ok": False, "message": str(exc)})

    # After max_attempts exhausted: return guidance text and no patch
    guidance = (
        remediation_text
        or "Review finding details and refactor the flagged function manually to satisfy the detector requirements."
    )
    return {
        "status": "failed",
        "unified_diff": "",
        "rationale": (
            f"Automated verification failed after {max_attempts} attempts. "
            f"Guidance: {guidance}. Last error: {failure_log}"
        ),
        "compiles": False if failure_log and "compilation" in failure_log.lower() else None,
        "finding_cleared": False,
        "new_findings": [],
        "gas_delta": {},
        "verification_log": last_log,
    }

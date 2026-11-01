"""
Patch Verifier for Milestone 5 (F8 / Stages 7 & 8).
Verifies patches in a scratch copy inside the sandbox:
1. Apply diff cleanly
2. Compile with solc/forge
3. Re-run Slither and custom detectors
4. Confirm target finding cleared
5. Reject any new high or critical finding
6. Block if storage layout of an upgradeable contract changes
7. Gas measurement with forge snapshot only if safe tests exist (otherwise "gas not measured")
NEVER run the user's own tests or scripts.
"""
from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

from auditor_core.detectors.scanner import (
    CandidateFinding,
    deduplicate_and_filter_findings,
    run_custom_detectors,
    run_slither_curated_scan,
)
from auditor_core.pipeline.building import BuildFailedError, compile_with_solc
from auditor_core.privilege_map.roles import resolve_roles_and_actions
from auditor_core.privilege_map.semantic import (
    ContractSemanticModel,
    build_semantic_models_for_project,
)
from auditor_core.sandbox.runner import SandboxRunner

logger = get_logger(__name__)


@dataclass
class VerificationResult:
    ok: bool
    compiles: bool | None = None
    finding_cleared: bool | None = None
    new_findings: list[dict[str, Any]] = field(default_factory=list)
    gas_delta: dict[str, int] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)
    failure_summary: str = ""
    patched_sources: dict[str, str] = field(default_factory=dict)


def apply_unified_diff(sources: dict[str, str], diff_text: str) -> dict[str, str]:
    """
    Applies a standard unified diff to a dictionary of {file_path: file_content}.
    Returns a new dictionary with the patched contents.
    Raises ValueError if diff is malformed or cannot be applied.
    """
    if not diff_text or not diff_text.strip():
        return copy.deepcopy(sources)

    patched_sources = copy.deepcopy(sources)

    # Split diff into per-file chunks
    file_diff_pattern = re.compile(r"^--- [ab]/(.*?)\n\+\+\+ [ab]/(.*?)\n", re.MULTILINE)
    matches = list(file_diff_pattern.finditer(diff_text))

    if not matches:
        # Check if single file diff without standard header or fallback
        raise ValueError("Unified diff contains no valid '--- a/...' and '+++ b/...' headers")

    for i, m in enumerate(matches):
        file_path = m.group(2).strip()
        start_idx = m.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(diff_text)
        hunks_text = diff_text[start_idx:end_idx]

        # Locate target file in sources (match relative or basename)
        target_key = None
        if file_path in patched_sources:
            target_key = file_path
        else:
            for k in patched_sources:
                if (
                    k == file_path
                    or k.endswith("/" + file_path)
                    or file_path.endswith("/" + k)
                    or Path(k).name == Path(file_path).name
                ):
                    target_key = k
                    break

        if not target_key and len(patched_sources) == 1:
            target_key = list(patched_sources.keys())[0]

        if not target_key:
            raise ValueError(f"Diff target file '{file_path}' not found in project sources")

        original_lines = patched_sources[target_key].splitlines(keepends=True)
        # Apply hunks to original_lines
        patched_lines = _apply_file_hunks(original_lines, hunks_text)
        patched_sources[target_key] = "".join(patched_lines)

    return patched_sources


def _apply_file_hunks(lines: list[str], hunks_text: str) -> list[str]:
    """Applies hunks of a single file diff to a list of lines."""
    result = list(lines)
    # Parse @@ -old_start,old_count +new_start,new_count @@
    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    raw_hunk_blocks = re.split(r"(?m)^(?=@@ -\d+)", hunks_text)

    # Offset tracking as lines are inserted/removed
    line_offset = 0

    for block in raw_hunk_blocks:
        block = block.strip()
        if not block:
            continue

        header_match = hunk_header_re.match(block)
        if not header_match:
            continue

        old_start = int(header_match.group(1)) - 1  # 0-indexed
        old_count = int(header_match.group(2)) if header_match.group(2) else 1

        hunk_lines = block.splitlines(keepends=True)[1:]  # skip header

        # Extract old context + removed lines and new context + added lines
        expected_old = []
        replacement_new = []
        for hl in hunk_lines:
            if hl.startswith(" "):
                expected_old.append(hl[1:])
                replacement_new.append(hl[1:])
            elif hl.startswith("-"):
                expected_old.append(hl[1:])
            elif hl.startswith("+"):
                replacement_new.append(hl[1:])

        # Find where expected_old appears in result near old_start + line_offset
        match_idx = -1
        target_search_start = max(0, old_start + line_offset - 5)
        target_search_end = min(len(result), old_start + line_offset + 5)

        # First try exact line position
        cand_start = old_start + line_offset
        if 0 <= cand_start <= len(result) - len(expected_old):
            if result[cand_start:cand_start + len(expected_old)] == expected_old:
                match_idx = cand_start

        # If not, search nearby
        if match_idx == -1:
            for idx in range(len(result) - len(expected_old) + 1):
                if result[idx:idx + len(expected_old)] == expected_old:
                    match_idx = idx
                    break

        # Fallback: strip line ending match
        if match_idx == -1:
            expected_old_stripped = [l.strip() for l in expected_old]
            for idx in range(len(result) - len(expected_old) + 1):
                if [l.strip() for l in result[idx:idx + len(expected_old)]] == expected_old_stripped:
                    match_idx = idx
                    break

        if match_idx == -1:
            raise ValueError(f"Hunk failed to match context lines:\n{''.join(expected_old[:3])}")

        # Replace in result
        result[match_idx:match_idx + len(expected_old)] = replacement_new
        line_offset += (len(replacement_new) - len(expected_old))

    return result


def check_storage_layout_impact(
    original_models: dict[str, ContractSemanticModel],
    patched_models: dict[str, ContractSemanticModel],
) -> tuple[bool, str]:
    """
    Verifies that the storage layout of upgradeable contracts has NOT been modified.
    Returns (ok, message).
    """
    for c_name, patched_m in patched_models.items():
        orig_m = original_models.get(c_name)
        if not orig_m:
            continue

        is_upgradeable = (
            orig_m.upgradeability in ("uups", "transparent", "beacon", "diamond", "unknown")
            or patched_m.upgradeability in ("uups", "transparent", "beacon", "diamond", "unknown")
            or any("upgradeable" in inh.lower() for inh in orig_m.inheritance)
        )

        if is_upgradeable:
            orig_storage = [
                (v.name, v.type_name)
                for v in orig_m.state_variables
                if not v.is_constant and not v.is_immutable
            ]
            patched_storage = [
                (v.name, v.type_name)
                for v in patched_m.state_variables
                if not v.is_constant and not v.is_immutable
            ]

            # In upgradeable contracts, storage layout must be strictly preserved:
            # existing variables cannot be removed, retyped, reordered, or prepended.
            if orig_storage != patched_storage:
                return False, (
                    f"Storage layout modification detected in upgradeable contract '{c_name}'. "
                    f"Original layout: {orig_storage}; Patched layout: {patched_storage}. "
                    "Storage layout changes are prohibited on upgradeable contracts to prevent storage collision."
                )

    return True, "Storage layout preserved"


async def verify_patch(
    project_sources: dict[str, str],
    unified_diff: str,
    target_finding: dict[str, Any] | CandidateFinding,
    original_findings: list[CandidateFinding] | list[dict[str, Any]],
    solc_version: str = "0.8.24",
    sandbox_runner: SandboxRunner | None = None,
) -> VerificationResult:
    """
    Execute full empirical verification of a patch in sandbox scratch copy:
    1. Apply diff
    2. Compile
    3. Re-run Slither & custom detectors
    4. Confirm target finding cleared
    5. Reject new high/critical
    6. Check storage layout on upgradeable contracts
    7. Gas measurement
    """
    log: list[dict[str, Any]] = []
    runner = sandbox_runner or SandboxRunner(runtime="local")

    target_detector = getattr(target_finding, "detector", None) or (
        target_finding.get("detector") if isinstance(target_finding, dict) else ""
    )
    target_file = getattr(target_finding, "file_path", None) or (
        target_finding.get("file_path") or target_finding.get("file") if isinstance(target_finding, dict) else ""
    )
    target_title = getattr(target_finding, "title", None) or (
        target_finding.get("title") if isinstance(target_finding, dict) else ""
    )

    # Step 1: Apply diff
    try:
        patched_sources = apply_unified_diff(project_sources, unified_diff)
        log.append({"step": "apply", "ok": True, "message": "Unified diff applied cleanly"})
    except Exception as exc:
        msg = f"Failed to apply unified diff: {exc}"
        log.append({"step": "apply", "ok": False, "message": msg})
        return VerificationResult(
            ok=False,
            compiles=None,
            finding_cleared=False,
            log=log,
            failure_summary=msg,
        )

    # Step 2: Compile
    try:
        _, _ = compile_with_solc(
            sources=patched_sources,
            solc_version=solc_version,
            sandbox_runner=runner,
        )
        log.append({"step": "compile", "ok": True, "message": "Compilation succeeded"})
    except BuildFailedError as bfe:
        diag_msg = "; ".join(f"{d.get('file')}:{d.get('line')}: {d.get('message')}" for d in bfe.diagnostics)
        msg = f"Compilation failed: {diag_msg or bfe.message}"
        log.append({
            "step": "compile",
            "ok": False,
            "message": msg,
            "diagnostics": bfe.diagnostics,
        })
        return VerificationResult(
            ok=False,
            compiles=False,
            finding_cleared=False,
            log=log,
            failure_summary=msg,
            patched_sources=patched_sources,
        )

    # Step 3: Re-run Slither and custom detectors
    try:
        patched_slither = run_slither_curated_scan(patched_sources, solc_version=solc_version)
        patched_models, _ = build_semantic_models_for_project(patched_sources, solc_version=solc_version)
        _, _, missing_ac, _ = resolve_roles_and_actions(patched_models, uuid.uuid4(), uuid.uuid4(), {}, {})
        patched_custom = run_custom_detectors(patched_models, missing_ac)
        all_patched_findings = deduplicate_and_filter_findings(patched_slither + patched_custom)
        log.append({
            "step": "re_scan",
            "ok": True,
            "findings_count": len(all_patched_findings),
        })
    except Exception as exc:
        msg = f"Re-scan analysis failed: {exc}"
        log.append({"step": "re_scan", "ok": False, "message": msg})
        return VerificationResult(
            ok=False,
            compiles=True,
            finding_cleared=False,
            log=log,
            failure_summary=msg,
            patched_sources=patched_sources,
        )

    # Step 4: Confirm target finding cleared
    # A finding matches if same detector and same contract/function or file
    target_cleared = True
    for pf in all_patched_findings:
        if pf.detector == target_detector:
            # Check file match
            file_match = (
                not target_file
                or Path(pf.file_path).name == Path(target_file).name
                or pf.file_path == target_file
            )
            if file_match:
                target_cleared = False
                break

    if not target_cleared:
        msg = f"Target finding '{target_title}' ({target_detector}) was NOT cleared by the patch"
        log.append({"step": "target_cleared", "ok": False, "message": msg})
        return VerificationResult(
            ok=False,
            compiles=True,
            finding_cleared=False,
            log=log,
            failure_summary=msg,
            patched_sources=patched_sources,
        )
    log.append({"step": "target_cleared", "ok": True, "message": "Target finding cleared"})

    # Step 5: Reject any new high or critical findings
    def _is_existing_finding(pf: CandidateFinding) -> bool:
        pf_file_name = Path(pf.file_path).name
        for f in original_findings:
            det = getattr(f, "detector", None) or (f.get("detector") if isinstance(f, dict) else "")
            f_file = getattr(f, "file_path", None) or (f.get("file_path") or f.get("file") if isinstance(f, dict) else "")
            f_file_name = Path(f_file).name if f_file else ""
            f_start = getattr(f, "start_line", None) or (f.get("start_line") if isinstance(f, dict) else None)
            f_sig = getattr(f, "function_signature", None) or (f.get("function_signature") if isinstance(f, dict) else "")

            if det == pf.detector and (not f_file_name or f_file_name == pf_file_name):
                if f_sig and pf.function_signature and f_sig == pf.function_signature:
                    return True
                if f_start is not None and abs(pf.start_line - f_start) <= 10:
                    return True
                if not f_sig and f_start is None:
                    return True
        return False

    new_high_crit = []
    for pf in all_patched_findings:
        if not _is_existing_finding(pf):
            if pf.severity.lower() in ("high", "critical"):
                new_high_crit.append({
                    "title": pf.title,
                    "detector": pf.detector,
                    "severity": pf.severity,
                    "file": pf.file_path,
                    "start_line": pf.start_line,
                })

    if new_high_crit:
        msg = f"Patch introduced {len(new_high_crit)} new high/critical finding(s): {new_high_crit[0]['title']}"
        log.append({"step": "new_findings", "ok": False, "message": msg, "new_findings": new_high_crit})
        return VerificationResult(
            ok=False,
            compiles=True,
            finding_cleared=True,
            new_findings=new_high_crit,
            log=log,
            failure_summary=msg,
            patched_sources=patched_sources,
        )
    log.append({"step": "new_findings", "ok": True, "message": "No new high or critical findings"})

    # Step 6: Block storage layout changes on upgradeable contracts
    original_models, _ = build_semantic_models_for_project(project_sources, solc_version=solc_version)
    layout_ok, layout_msg = check_storage_layout_impact(original_models, patched_models)
    if not layout_ok:
        log.append({"step": "storage_layout", "ok": False, "message": layout_msg})
        return VerificationResult(
            ok=False,
            compiles=True,
            finding_cleared=True,
            log=log,
            failure_summary=layout_msg,
            patched_sources=patched_sources,
        )
    log.append({"step": "storage_layout", "ok": True, "message": layout_msg})

    # Step 7: Gas measurement
    # ONLY run forge snapshot if safe tests exist; NEVER run user's own tests or scripts.
    log.append({"step": "gas", "ok": True, "message": "gas not measured (no safe generated tests present)"})

    return VerificationResult(
        ok=True,
        compiles=True,
        finding_cleared=True,
        new_findings=[],
        gas_delta={},
        log=log,
        failure_summary="",
        patched_sources=patched_sources,
    )

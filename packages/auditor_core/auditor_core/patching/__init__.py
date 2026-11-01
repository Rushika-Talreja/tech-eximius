"""Patch generation and verification package."""
from auditor_core.patching.planner import (
    PatchHunk,
    PatchPlan,
    extract_minimal_code_slice,
    plan_patch,
    render_unified_diff,
)
from auditor_core.patching.service import generate_and_verify_patch
from auditor_core.patching.verifier import (
    VerificationResult,
    apply_unified_diff,
    check_storage_layout_impact,
    verify_patch,
)

__all__ = [
    "PatchHunk",
    "PatchPlan",
    "VerificationResult",
    "apply_unified_diff",
    "check_storage_layout_impact",
    "extract_minimal_code_slice",
    "generate_and_verify_patch",
    "plan_patch",
    "render_unified_diff",
    "verify_patch",
]

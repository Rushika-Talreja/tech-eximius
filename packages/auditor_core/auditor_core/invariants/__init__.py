"""
Invariants module (Milestone 7 / Stage 10).
"""
from auditor_core.invariants.classifier import classify_contract_type_with_confidence
from auditor_core.invariants.loader import InvariantTemplate, load_invariant_templates
from auditor_core.invariants.runner import (
    InvariantRunResult,
    run_invariant_suite_for_contract,
)

__all__ = [
    "InvariantRunResult",
    "InvariantTemplate",
    "classify_contract_type_with_confidence",
    "load_invariant_templates",
    "run_invariant_suite_for_contract",
]

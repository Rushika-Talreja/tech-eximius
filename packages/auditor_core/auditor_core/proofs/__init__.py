"""
Proofs module (Milestone 6 / Stage 9).
"""
from auditor_core.proofs.drafter import (
    ProofTestDraft,
    draft_proof_test,
    is_detector_supported,
    validate_test_asserts_rule_or_gain,
)
from auditor_core.proofs.verifier import ProofVerificationResult, verify_proof_test

__all__ = [
    "ProofTestDraft",
    "ProofVerificationResult",
    "draft_proof_test",
    "is_detector_supported",
    "validate_test_asserts_rule_or_gain",
    "verify_proof_test",
]

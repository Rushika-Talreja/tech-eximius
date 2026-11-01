"""
LLM Exploit Proof Drafter for Milestone 6 (F5 / Stage 9).
Drafts a Foundry test against the original contract for supported detectors.
Supported detectors:
- reentrancy
- missing access control
- unchecked call
- simple oracle read
"""
from __future__ import annotations

import re

from app.logging_config import get_logger
from pydantic import BaseModel

from auditor_core.llm.client import LLMClient

logger = get_logger(__name__)

SUPPORTED_DETECTOR_CLASSES = {
    "reentrancy": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-benign", "reentrancy", "reentrancy_classic"],
    "missing access control": ["missing-access-control", "unprotected-upgrade", "arbitrary-send-erc20", "arbitrary-send-eth", "unprotected-admin", "unguarded-admin", "access-control"],
    "unchecked call": ["unchecked-low-level-call", "unchecked-call", "unchecked-transfer", "unchecked_call"],
    "simple oracle read": ["oracle-read", "price-manipulation", "simple_oracle_read"],
}


class ProofTestDraft(BaseModel):
    test_contract_name: str
    test_source: str
    vulnerability_type: str
    attacker_gain_rule: str


def is_detector_supported(detector_name: str, title: str = "", description: str = "") -> tuple[bool, str]:
    """Check if a detector/finding is supported for automated exploit proof generation."""
    query = f"{detector_name} {title} {description}".lower()

    for category, keywords in SUPPORTED_DETECTOR_CLASSES.items():
        for kw in keywords:
            if kw in query:
                return True, category
        if category in query:
            return True, category

    return False, ""


def validate_test_asserts_rule_or_gain(test_source: str) -> tuple[bool, str]:
    """
    Validate that the generated test asserts an attacker gain or a broken rule.
    Rejects trivial tests that pass unconditionally.
    """
    if not test_source or not test_source.strip():
        return False, "Test source is empty"

    # Must contain assertions
    has_assertion = bool(re.search(r"\b(assertEq|assertGt|assertLt|assertTrue|assertFalse|assert|require)\b", test_source))
    if not has_assertion:
        return False, "Test contains no assertions (assertEq/assertGt/assertTrue/etc.)"

    # Must assert an attacker gain or broken rule
    gain_or_rule_patterns = [
        r"attacker",
        r"drain",
        r"balance",
        r"stolen",
        r"gain",
        r"profit",
        r"exploit",
        r"revert",
        r"broken",
        r"unauthorized",
        r"stolen",
        r"victim",
        r"preserv",
    ]
    has_gain_or_rule = any(re.search(pat, test_source, re.IGNORECASE) for pat in gain_or_rule_patterns)
    if not has_gain_or_rule:
        return False, "Test does not assert an attacker gain or broken security rule"

    return True, ""


async def draft_proof_test(
    contract_name: str,
    original_source: str,
    finding_title: str,
    finding_detector: str,
    finding_description: str,
) -> ProofTestDraft:
    """
    Invoke LLMClient to draft a Foundry test against the original contract.
    """
    supported, category = is_detector_supported(finding_detector, finding_title, finding_description)
    if not supported:
        raise ValueError(f"Detector '{finding_detector}' ({finding_title}) is not in the supported detector set for proofs")

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert Foundry smart contract security engineer. "
                "Draft a runnable Foundry test against the ORIGINAL contract that demonstrates the vulnerability. "
                "The test must assert an attacker gain or a broken rule (e.g. assertTrue victim balance is preserved, "
                "which fails on the original vulnerable code and passes on the patched code). "
                "Output strictly matching the ProofTestDraft JSON schema."
            ),
        },
        {
            "role": "user",
            "content": (
                f"<contract_name>{contract_name}</contract_name>\n"
                f"<vulnerability_class>{category}</vulnerability_class>\n"
                f"<finding>\nTitle: {finding_title}\nDetector: {finding_detector}\nDescription: {finding_description}\n</finding>\n"
                f"<contract_source>\n{original_source}\n</contract_source>\n"
            ),
        },
    ]

    draft: ProofTestDraft = await LLMClient.structured(
        ProofTestDraft,
        messages=messages,
        model_tier="reasoning",
    )

    valid, reason = validate_test_asserts_rule_or_gain(draft.test_source)
    if not valid:
        raise ValueError(f"Drafted test failed validation: {reason}")

    return draft

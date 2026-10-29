"""Deterministic claim verification for the auditor pipeline.

The verifier is the grounding gate between a drafted audit finding and the
retrieved corpus. It never calls a model: it only checks whether a drafted
claim carries a quote that appears *verbatim* inside a retrieved evidence
chunk, so the same draft and the same evidence always produce the same
result.

A claim is promoted to :class:`VerifiedFinding` only when its
``quoted_evidence`` is an exact substring of some
:class:`~auditor_core.rag.retrieval.Evidence` quote. Claims that cannot be
grounded are demoted to ungrounded observations and their severity is
clamped to ``Informational``. Every free-text field is scrubbed of
prompt-injection triggers before it is returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from auditor_core.rag.retrieval import Evidence

__all__ = [
    "Claim",
    "VerificationResult",
    "VerifiedFinding",
    "verify_draft",
]

#: Severity applied to every claim that could not be grounded.
UNGROUNDED_SEVERITY = "Informational"

#: Patterns stripped from every returned free-text field. Order matters:
#: script blocks and comments are removed before the generic tag matcher.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<\s*script\b.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>"),
    re.compile(
        r"\[\s*ignore\s+(?:all\s+)?previous\s+instructions\s*\]",
        re.IGNORECASE,
    ),
    re.compile(r"\bSYSTEM\s*:", re.IGNORECASE),
)


@dataclass
class Claim:
    """A single finding proposed by the drafting stage, before grounding."""

    claim_id: str
    title: str
    description: str
    swc_id: str | None
    severity: str
    quoted_evidence: str | None


@dataclass
class VerifiedFinding:
    """A claim whose quote was found verbatim in the retrieved corpus."""

    claim_id: str
    title: str
    severity: str
    doc_id: str
    source_url: str
    exact_quote: str
    grounded: bool


@dataclass
class VerificationResult:
    """Grounding outcome for a whole draft."""

    verified_findings: list[VerifiedFinding]
    unscored_observations: list[Claim]
    grounding_rate: float


def verify_draft(
    draft_claims: list[Claim],
    retrieved_evidence: list[Evidence],
    strict_quote_check: bool = True,
) -> VerificationResult:
    """Ground *draft_claims* against *retrieved_evidence*.

    Args:
        draft_claims: Claims produced by the drafting stage.
        retrieved_evidence: Evidence chunks returned by the retriever.
        strict_quote_check: When ``True`` a claim is grounded only if its
            quote is a byte-for-byte substring of an evidence quote. When
            ``False`` the comparison ignores case and repeated whitespace.

    Returns:
        A :class:`VerificationResult` holding the grounded findings, the
        demoted observations and the grounding rate.
    """
    findings: list[VerifiedFinding] = []
    observations: list[Claim] = []

    for claim in draft_claims:
        match = _match_evidence(
            claim.quoted_evidence, retrieved_evidence, strict_quote_check
        )
        if match is None:
            observations.append(_demote(claim))
            continue

        evidence, quote = match
        findings.append(
            VerifiedFinding(
                claim_id=claim.claim_id,
                title=_sanitize(claim.title) or "",
                severity=claim.severity,
                doc_id=evidence.doc_id,
                source_url=evidence.source_url,
                exact_quote=_sanitize(quote) or "",
                grounded=True,
            )
        )

    grounding_rate = len(findings) / len(draft_claims) if draft_claims else 0.0
    return VerificationResult(
        verified_findings=findings,
        unscored_observations=observations,
        grounding_rate=grounding_rate,
    )


def _match_evidence(
    quote: str | None,
    evidence: list[Evidence],
    strict: bool,
) -> tuple[Evidence, str] | None:
    """Return the first evidence carrying *quote*, or ``None``.

    Evidence is scanned in the order it was retrieved, so the strongest
    (top-ranked) match wins and the result is deterministic.
    """
    if not quote:
        return None

    needle = quote if strict else _normalise(quote)
    for item in evidence:
        haystack = item.exact_quote if strict else _normalise(item.exact_quote)
        if needle in haystack:
            return item, quote
    return None


def _normalise(text: str) -> str:
    """Case-fold and collapse whitespace for the relaxed comparison."""
    return " ".join(text.split()).casefold()


def _demote(claim: Claim) -> Claim:
    """Return an ungrounded copy of *claim* with sanitised, clamped fields."""
    return replace(
        claim,
        title=_sanitize(claim.title) or "",
        description=_sanitize(claim.description) or "",
        quoted_evidence=_sanitize(claim.quoted_evidence),
        severity=UNGROUNDED_SEVERITY,
    )


def _sanitize(text: str | None) -> str | None:
    """Strip prompt-injection triggers from *text*.

    Only the matched triggers are removed; the remaining text is left
    untouched apart from surrounding whitespace so grounded quotes stay
    verbatim when they carry no injection payload.
    """
    if text is None:
        return None

    cleaned = text
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return cleaned.strip()

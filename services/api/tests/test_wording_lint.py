"""
Wording lint test:
Verifies that no template or generator outputs 'safe', 'secure', 'audited', 'certified',
or 'compliant' as a verdict.
Ensures that 'No verified issues detected by this analysis' is used for clean outcomes.
"""
from __future__ import annotations

import re
from pathlib import Path


FORBIDDEN_VERDICTS = [
    r"\bverdict\s*:\s*[\"']?safe\b",
    r"\bverdict\s*:\s*[\"']?secure\b",
    r"\bverdict\s*:\s*[\"']?audited\b",
    r"\bverdict\s*:\s*[\"']?certified\b",
    r"\bverdict\s*:\s*[\"']?compliant\b",
    r"\bcontract is safe\b",
    r"\bcontract is secure\b",
    r"\bcontract is certified\b",
    r"\bcontract is compliant\b",
]


def test_wording_lint_across_codebase():
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    scan_dirs = [
        repo_root / "packages" / "auditor_core",
        repo_root / "services" / "api" / "app" / "routers",
    ]

    extensions = {".py", ".yaml", ".yml", ".json"}
    violations = []

    for s_dir in scan_dirs:
        for p in s_dir.rglob("*"):
            if not p.is_file() or p.suffix not in extensions:
                continue
            if "__pycache__" in str(p) or ".pytest_cache" in str(p):
                continue

            content = p.read_text(encoding="utf-8", errors="replace")
            for pattern in FORBIDDEN_VERDICTS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    violations.append(f"{p}: matches forbidden verdict pattern '{pattern}': {match.group(0)}")

    assert not violations, "Found forbidden verdict wording:\n" + "\n".join(violations)


def test_clean_verdict_string():
    from app.routers.exports import CLEAN_VERDICT
    assert CLEAN_VERDICT == "No verified issues detected by this analysis"


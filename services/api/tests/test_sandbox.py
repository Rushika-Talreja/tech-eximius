"""
Sandbox execution and security isolation tests.
Enforces AGENTS.md Hard Rule #4: No network in analysis sandboxes.
Verifies that any network request from inside the analysis sandbox strictly FAILS.
"""
from __future__ import annotations

import sys
import pytest
from auditor_core.sandbox.runner import SandboxRunner


def test_sandbox_network_request_fails() -> None:
    """
    Test that attempting a network connection from inside the analysis sandbox FAILS.
    Analysis sandbox runs with allow_network=False.
    """
    runner = SandboxRunner(runtime="local", timeout_seconds=10)

    # Command attempting outbound HTTP/network connection
    probe_script = (
        "import sys, urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=3)\n"
        "    sys.exit(0)\n"  # Succeeded (violation)
        "except Exception as e:\n"
        "    print(f'BLOCKED_AS_EXPECTED: {e}')\n"
        "    sys.exit(42)\n"  # Failed (expected)
    )

    result = runner.run(
        cmd=[sys.executable, "-c", probe_script],
        allow_network=False,
    )

    # Must exit with non-zero (42) and not exit with 0
    assert result.exit_code != 0, "Network connection unexpectedly succeeded inside analysis sandbox"
    assert "BLOCKED_AS_EXPECTED" in result.stdout or result.exit_code == 42


def test_sandbox_strips_secrets_from_env() -> None:
    """
    Test that sensitive environment variables (AWS keys, DB URLs, Peppers)
    are stripped from sandbox processes.
    """
    runner = SandboxRunner(runtime="local", timeout_seconds=10)

    probe_script = (
        "import os, json; "
        "print(json.dumps(dict(os.environ)))"
    )

    # Simulate environment with secrets
    import os
    original = dict(os.environ)
    try:
        os.environ["DATABASE_URL"] = "postgresql://user:supersecret@localhost/db"
        os.environ["API_KEY_HASH_PEPPER"] = "top-secret-pepper-phrase"
        os.environ["S3_SECRET_KEY"] = "minio-admin-secret"

        result = runner.run(
            cmd=[sys.executable, "-c", probe_script],
            allow_network=False,
        )

        assert result.exit_code == 0
        assert "supersecret" not in result.stdout
        assert "top-secret-pepper-phrase" not in result.stdout
        assert "minio-admin-secret" not in result.stdout
    finally:
        os.environ.clear()
        os.environ.update(original)

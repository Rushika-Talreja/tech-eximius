"""
Log scrub tests.
Ensures customer code and sensitive fields (source, code, diff, prompt, completion)
are never present in logs or echoed in error responses.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.logging_config import _scrub_dict_recursive, _scrub_event_dict


def test_unit_log_scrub_filter() -> None:
    """Unit test the logging filter: forbidden fields must be stripped."""
    forbidden = ["source", "code", "diff", "prompt", "completion"]

    # 1. Top-level forbidden fields
    event: dict[str, Any] = {
        "event": "audit_pipeline_step",
        "org_id": str(uuid.uuid4()),
        "source": "contract Vault { function drain() external {} }",
        "code": "uint256 balance = 100;",
        "diff": "--- a/Vault.sol\n+++ b/Vault.sol",
        "prompt": "Analyze this smart contract for reentrancy bugs",
        "completion": "Vulnerability identified: reentrancy in withdraw()",
        "stage": "static_analysis",
        "safe_meta": {"status": "ok"},
    }

    result = _scrub_event_dict(logging.getLogger("test"), "info", event)
    for field in forbidden:
        assert field not in result, f"Field '{field}' was not scrubbed from log event"

    assert result["event"] == "audit_pipeline_step"
    assert result["stage"] == "static_analysis"
    assert result["safe_meta"] == {"status": "ok"}

    # 2. Nested forbidden fields
    nested_event: dict[str, Any] = {
        "event": "nested_check",
        "nested": {
            "source": "pragma solidity ^0.8.0;",
            "code": "selfdestruct(payable(msg.sender));",
            "allowed": True,
        },
    }
    nested_result = _scrub_event_dict(logging.getLogger("test"), "info", nested_event)
    assert "source" not in nested_result["nested"]
    assert "code" not in nested_result["nested"]
    assert nested_result["nested"]["allowed"] is True


@pytest.mark.asyncio
async def test_integration_logs_and_errors_do_not_echo_payloads(
    async_client: AsyncClient,
    auth_a: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Integration test:
    - Send request with unique marker string
    - Ensure marker string does not appear in application logs
    - Ensure validation error (422) does not echo request body/marker
    """
    marker = "UNIQUE_CUSTOMER_SECRET_PAYLOAD_TOKEN_778899"

    with caplog.at_level(logging.INFO):
        # 1. Successful request with marker
        resp = await async_client.post(
            "/v1/projects",
            json={"name": "Log Test Project", "description": marker},
            headers=auth_a,
        )
        assert resp.status_code == 201

        # Check application logs for the marker
        for record in caplog.records:
            assert marker not in record.getMessage(), f"Customer payload leaked in log record ({record.name})"

        # 2. Invalid request causing 422 validation error
        caplog.clear()
        bad_resp = await async_client.post(
            "/v1/projects",
            json={"name": 12345, "invalid_field": marker, "description": marker},
            headers=auth_a,
        )
        assert bad_resp.status_code == 422
        bad_json = bad_resp.json()

        # Ensure error response body does NOT echo the marker
        raw_error_text = bad_resp.text
        assert marker not in raw_error_text, "Customer payload marker was echoed in 422 error response"

        # Ensure logs during 422 do not leak the marker
        for record in caplog.records:
            assert marker not in record.getMessage(), "Customer payload leaked in error log"

"""
Test error format envelope and status codes.
Spec requirement:
Every error returns:
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {...},
    "request_id": "..."
  }
}
Assert status 401, 403, 404, 422, 429.
Assert X-Request-Id header matches error.request_id.
Assert 429 includes Retry-After, X-RateLimit-Limit, and X-RateLimit-Remaining headers.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


def _assert_error_envelope(response_data: dict, expected_code: str, expected_request_id: str | None) -> None:
    assert "error" in response_data, f"Missing 'error' envelope in {response_data}"
    err = response_data["error"]
    assert err["code"] == expected_code
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert isinstance(err["details"], dict)
    assert "request_id" in err
    if expected_request_id:
        assert err["request_id"] == expected_request_id


@pytest.mark.asyncio
async def test_error_format_401(async_client: AsyncClient) -> None:
    req_id = f"test-req-{uuid.uuid4()}"
    resp = await async_client.get("/v1/me", headers={"X-Request-Id": req_id})
    assert resp.status_code == 401
    assert resp.headers.get("X-Request-Id") == req_id
    _assert_error_envelope(resp.json(), "UNAUTHENTICATED", req_id)


@pytest.mark.asyncio
async def test_error_format_403(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    # Create read-only key
    key_resp = await async_client.post(
        "/v1/api-keys",
        json={"name": "ro-key", "scopes": ["audits:read"]},
        headers=auth_a,
    )
    assert key_resp.status_code == 201
    ro_key = key_resp.json()["key"]

    req_id = f"test-req-{uuid.uuid4()}"
    resp = await async_client.post(
        "/v1/projects",
        json={"name": "Forbidden Project"},
        headers={"X-API-Key": ro_key, "X-Request-Id": req_id},
    )
    assert resp.status_code == 403
    assert resp.headers.get("X-Request-Id") == req_id
    _assert_error_envelope(resp.json(), "FORBIDDEN", req_id)


@pytest.mark.asyncio
async def test_error_format_404(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    req_id = f"test-req-{uuid.uuid4()}"
    non_existent_id = str(uuid.uuid4())
    resp = await async_client.get(
        f"/v1/projects/{non_existent_id}",
        headers={**auth_a, "X-Request-Id": req_id},
    )
    assert resp.status_code == 404
    assert resp.headers.get("X-Request-Id") == req_id
    _assert_error_envelope(resp.json(), "NOT_FOUND", req_id)


@pytest.mark.asyncio
async def test_error_format_422(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    req_id = f"test-req-{uuid.uuid4()}"
    # Send body missing required field 'name'
    resp = await async_client.post(
        "/v1/projects",
        json={"invalid_field": 123},
        headers={**auth_a, "X-Request-Id": req_id},
    )
    assert resp.status_code == 422
    assert resp.headers.get("X-Request-Id") == req_id
    _assert_error_envelope(resp.json(), "VALIDATION_ERROR", req_id)
    assert "errors" in resp.json()["error"]["details"]


@pytest.mark.asyncio
async def test_error_format_429(async_client: AsyncClient) -> None:
    # First request: within limit (limit is 1 per minute on test endpoint)
    first_resp = await async_client.get("/v1/test-rate-limit")
    assert first_resp.status_code == 200
    assert "X-RateLimit-Limit" in first_resp.headers
    assert "X-RateLimit-Remaining" in first_resp.headers

    # Second request: exceeds rate limit
    req_id = f"test-req-{uuid.uuid4()}"
    second_resp = await async_client.get(
        "/v1/test-rate-limit",
        headers={"X-Request-Id": req_id},
    )
    assert second_resp.status_code == 429
    assert second_resp.headers.get("X-Request-Id") == req_id
    assert "Retry-After" in second_resp.headers
    assert "X-RateLimit-Limit" in second_resp.headers
    assert "X-RateLimit-Remaining" in second_resp.headers
    assert second_resp.headers["X-RateLimit-Remaining"] == "0"
    _assert_error_envelope(second_resp.json(), "RATE_LIMITED", req_id)


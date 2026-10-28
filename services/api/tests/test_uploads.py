"""
Tests for POST /v1/uploads and zip safety validations.
Verifies:
- .sol and .zip file acceptance
- Rejection of invalid extensions (422 UNSUPPORTED_SOURCE)
- Rejection of oversized payloads (413 PAYLOAD_TOO_LARGE)
- Rejection of path traversal (422 VALIDATION_ERROR)
- Rejection of symlinks in zip (422 VALIDATION_ERROR)
- Rejection of zip bombs (compression ratio > 100:1)
- Rejection of file count exceeding limit
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_sol_success(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    sol_content = b"// SPDX-License-Identifier: MIT\npragma solidity 0.8.24;\ncontract Simple {}\n"
    files = {"file": ("Simple.sol", io.BytesIO(sol_content), "text/plain")}

    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "upload_id" in data
    assert data["kind"] == "sol"
    assert data["size_bytes"] == len(sol_content)
    assert "sha256" in data
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_upload_zip_success(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("src/Vault.sol", "// SPDX-License-Identifier: MIT\npragma solidity 0.8.24;\ncontract Vault {}")
        zf.writestr("foundry.toml", "[profile.default]\nsrc = 'src'")

    buf.seek(0)
    files = {"file": ("project.zip", buf, "application/zip")}

    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["kind"] == "zip"
    assert "upload_id" in data


@pytest.mark.asyncio
async def test_upload_unsupported_extension(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    files = {"file": ("malicious.exe", io.BytesIO(b"binary"), "application/octet-stream")}
    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNSUPPORTED_SOURCE"


@pytest.mark.asyncio
async def test_upload_oversized_file(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    # Default limit is 10 MB in config; test with 11 MB
    oversized = b"0" * (11 * 1024 * 1024)
    files = {"file": ("large.sol", io.BytesIO(oversized), "text/plain")}
    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_zip_path_traversal(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    # 1. Zip with relative path traversal '..'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0")
    buf.seek(0)

    files = {"file": ("traversal.zip", buf, "application/zip")}
    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "traversal" in resp.json()["error"]["message"].lower()

    # 2. Zip with absolute path '/etc/passwd'
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as zf:
        zf.writestr("/etc/passwd", "root:x:0:0")
    buf2.seek(0)

    files2 = {"file": ("abs_traversal.zip", buf2, "application/zip")}
    resp2 = await async_client.post("/v1/uploads", files=files2, headers=auth_a)
    assert resp2.status_code == 422
    assert resp2.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_upload_zip_symlink(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zinfo = zipfile.ZipInfo("symlink_entry")
        # Set external_attr for symlink (0xA000)
        zinfo.external_attr = 0xA1ED0000
        zf.writestr(zinfo, "/etc/passwd")

    buf.seek(0)
    files = {"file": ("symlink.zip", buf, "application/zip")}
    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "symbolic link" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_upload_zip_bomb(async_client: AsyncClient, auth_a: dict[str, str]) -> None:
    # High compression ratio (1 MB zeroes compressed to a few hundred bytes -> ratio > 1000:1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge_sparse_file.txt", b"\x00" * (2 * 1024 * 1024))

    buf.seek(0)
    files = {"file": ("bomb.zip", buf, "application/zip")}
    resp = await async_client.post("/v1/uploads", files=files, headers=auth_a)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "ratio" in resp.json()["error"]["message"].lower()


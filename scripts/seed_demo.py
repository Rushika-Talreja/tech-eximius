#!/usr/bin/env python3
"""
Seed script for DeFi Contract Auditor Demo.
Seeds three core demo contracts:
  1. Ownable Vault (unbounded mint & withdraw) -> Flagship Privilege Map
  2. Role-Based Token (AccessControl hierarchy) -> Multi-role governance
  3. Classic Reentrancy (withdraw before balance update) -> Automated Patch & Proof
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure correct PYTHONPATH (services/api first so app.main imports FastAPI app)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "services" / "worker"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "auditor_core"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "schemas"))
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

import httpx
from app.config import get_settings
from app.db.models import init_local_db
from app.devtools.mint_token import mint_token
from app.main import app

FIXTURES_DIR = REPO_ROOT / "fixtures" / "contracts"


async def seed_audit(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    project_name: str,
    project_desc: str,
    sol_filename: str,
    sol_content: bytes,
    features: list[str],
) -> dict[str, Any]:
    """Create project, upload contract, create audit, wait for completion, and return audit data."""
    print(f"\n[*] Seeding: {project_name} ({sol_filename})...")

    # 1. Create project
    proj_resp = await client.post(
        "/v1/projects",
        json={"name": project_name, "description": project_desc},
        headers=auth_headers,
    )
    if proj_resp.status_code != 201:
        raise RuntimeError(f"Failed to create project: {proj_resp.status_code} {proj_resp.text}")
    project_data = proj_resp.json()
    project_id = project_data["id"]

    # 2. Upload contract
    files = {"file": (sol_filename, io.BytesIO(sol_content), "text/plain")}
    up_resp = await client.post("/v1/uploads", files=files, headers=auth_headers)
    if up_resp.status_code != 201:
        raise RuntimeError(f"Failed to upload {sol_filename}: {up_resp.status_code} {up_resp.text}")
    upload_id = up_resp.json()["upload_id"]

    # 3. Create audit
    audit_resp = await client.post(
        f"/v1/projects/{project_id}/audits",
        json={
            "upload_id": upload_id,
            "options": {"features": features, "solc_version": "0.8.24"},
        },
        headers=auth_headers,
    )
    if audit_resp.status_code != 202:
        raise RuntimeError(f"Failed to start audit: {audit_resp.status_code} {audit_resp.text}")
    audit_id = audit_resp.json()["audit_id"]

    # 4. Wait for audit completion
    print(f"    - Waiting for pipeline completion (Audit ID: {audit_id})...")
    status = "queued"
    for _ in range(60):
        await asyncio.sleep(0.2)
        get_res = await client.get(f"/v1/audits/{audit_id}", headers=auth_headers)
        if get_res.status_code == 200:
            status = get_res.json().get("status", "")
            if status in ("complete", "failed"):
                break

    if status != "complete":
        print(f"    [!] Warning: Audit ended with status {status}")

    # Fetch results
    findings_resp = await client.get(f"/v1/audits/{audit_id}/findings", headers=auth_headers)
    findings = findings_resp.json().get("items", []) if findings_resp.status_code == 200 else []

    priv_resp = await client.get(f"/v1/audits/{audit_id}/privilege-map", headers=auth_headers)
    priv_data = priv_resp.json() if priv_resp.status_code == 200 else {}

    # Trigger patch for first finding if any
    patch_id = None
    if findings:
        target_f = findings[0]
        f_id = target_f["id"]
        patch_res = await client.post(
            f"/v1/audits/{audit_id}/findings/{f_id}/patches",
            headers=auth_headers,
        )
        if patch_res.status_code == 202:
            patch_id = patch_res.json().get("patch_id")
            # Wait briefly for patch generation
            for _ in range(30):
                await asyncio.sleep(0.2)
                p_get = await client.get(f"/v1/audits/{audit_id}/findings/{f_id}/patches", headers=auth_headers)
                if p_get.status_code == 200 and p_get.json().get("items"):
                    break

    # Trigger proof if proofs enabled and finding is reentrancy
    proof_id = None
    if "proofs" in features and findings:
        for f in findings:
            if "reentrancy" in f.get("title", "").lower() or "reentrancy" in f.get("detector", "").lower():
                proof_res = await client.post(
                    f"/v1/audits/{audit_id}/findings/{f['id']}/proof",
                    headers=auth_headers,
                )
                if proof_res.status_code == 201:
                    proof_id = proof_res.json().get("id")
                break

    print(f"    [+] {project_name} ready: {len(findings)} findings, {len(priv_data.get('results', []))} roles")
    return {
        "project_id": project_id,
        "audit_id": audit_id,
        "name": project_name,
        "filename": sol_filename,
        "findings_count": len(findings),
        "patch_id": patch_id,
        "proof_id": proof_id,
        "privilege_map": priv_data,
    }


async def main() -> None:
    # Enable feature flags for demo
    settings = get_settings()
    settings.proofs_enabled = True
    settings.invariants_enabled = True

    await init_local_db()

    token = mint_token("a")
    headers = {"Authorization": f"Bearer {token}"}

    # Connect via ASGITransport or live HTTP
    use_live_http = False
    try:
        async with httpx.AsyncClient(timeout=1.0) as check_client:
            res = await check_client.get("http://localhost:8000/v1/health")
            if res.status_code == 200:
                use_live_http = True
    except Exception:
        use_live_http = False

    if use_live_http:
        print("[*] Connecting to live running API on http://localhost:8000...")
        transport = None
        base_url = "http://localhost:8000"
    else:
        print("[*] Running against in-process ASGI auditor application...")
        transport = httpx.ASGITransport(app=app)
        base_url = "http://localhost:8000"

    results = {}

    async with httpx.AsyncClient(transport=transport, base_url=base_url, timeout=60.0) as client:
        # Contract 1: Ownable Vault
        vault_path = FIXTURES_DIR / "vault_basic" / "Vault.sol"
        vault_code = vault_path.read_bytes()
        c1 = await seed_audit(
            client=client,
            auth_headers=headers,
            project_name="Demo: Yield Vault (Ownable)",
            project_desc="ERC-4626 multi-asset yield vault with admin withdraw and mint capabilities",
            sol_filename="Vault.sol",
            sol_content=vault_code,
            features=["privilege_map", "findings", "patches", "invariants"],
        )
        results["vault"] = c1

        # Contract 2: Access Control Token
        token_path = FIXTURES_DIR / "token_accesscontrol" / "Token.sol"
        token_code = token_path.read_bytes()
        c2 = await seed_audit(
            client=client,
            auth_headers=headers,
            project_name="Demo: Access Control Token",
            project_desc="ERC20 Governance Token with DEFAULT_ADMIN_ROLE, MINTER_ROLE, and PAUSER_ROLE",
            sol_filename="Token.sol",
            sol_content=token_code,
            features=["privilege_map", "findings", "patches", "invariants"],
        )
        results["token"] = c2

        # Contract 3: Classic Reentrancy
        reent_path = FIXTURES_DIR / "reentrancy_classic" / "ReentrancyClassic.sol"
        reent_code = reent_path.read_bytes()
        c3 = await seed_audit(
            client=client,
            auth_headers=headers,
            project_name="Demo: Classic Reentrancy",
            project_desc="Vulnerable pool contract with external call before state balance reset",
            sol_filename="ReentrancyClassic.sol",
            sol_content=reent_code,
            features=["privilege_map", "findings", "patches", "proofs", "invariants"],
        )
        results["reentrancy"] = c3

        # Record demo state to a JSON file for quick UI reference / offline fallback
        demo_state_file = REPO_ROOT / "data" / "demo_state.json"
        demo_state_file.parent.mkdir(parents=True, exist_ok=True)
        demo_state_file.write_text(json.dumps(results, indent=2, default=str))

        # Generate recorded fallback file for the UI
        fallback_data = await generate_recorded_fallback(client, headers, results)
        fallback_path = REPO_ROOT / "data" / "demoFallback.json"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(json.dumps(fallback_data, indent=2, default=str))
        print(f"\n[+] Generated UI recorded fallback at {fallback_path}")

    # Print Clean Formatted Summary
    vault_id = results["vault"]["audit_id"]
    token_id = results["token"]["audit_id"]
    reent_id = results["reentrancy"]["audit_id"]

    console_base = "http://localhost:3000"

    print("\n" + "=" * 68)
    print("           === DEFI CONTRACT AUDITOR DEMO READY ===")
    print("=" * 68)
    print(f"\n  Console URL:        {console_base}")
    print(f"  API Health Probe:   http://localhost:8000/v1/health")
    print(f"  Interactive Docs:   http://localhost:8000/docs")
    print("\n  Direct Feature Links:")
    print(f"  * 1. Privilege Map (Ownable Vault):")
    print(f"       {console_base}/privilege-map?audit_id={vault_id}")
    print(f"  * 2. Multi-Role Hierarchy (Token):")
    print(f"       {console_base}/privilege-map?audit_id={token_id}")
    print(f"  * 3. Reentrancy Findings & Evidence:")
    print(f"       {console_base}/findings?audit_id={reent_id}")
    print(f"  * 4. Automated Patch & Verification (Reentrancy):")
    print(f"       {console_base}/patches?audit_id={reent_id}")
    print(f"  * 5. Exploit Proofs & Invariant Checks:")
    print(f"       {console_base}/proofs?audit_id={reent_id}")
    print("=" * 68 + "\n")


async def generate_recorded_fallback(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    results: dict[str, Any],
) -> dict[str, Any]:
    """Capture full JSON responses from the seeded audits to embed as offline recorded fallback."""
    fallback: dict[str, Any] = {
        "_meta": {
            "source": "recorded",
            "description": "Pre-generated fallback analysis results for demo resilience",
        },
        "audits": {},
        "privilege_maps": {},
        "findings": {},
        "patches": {},
        "proofs": {},
        "invariants": {},
        "files": {},
    }

    proj_res = await client.get("/v1/projects", headers=headers)
    if proj_res.status_code == 200:
        fallback["projects"] = proj_res.json()

    for key, data in results.items():
        aid = data["audit_id"]

        # Audit
        res = await client.get(f"/v1/audits/{aid}", headers=headers)
        if res.status_code == 200:
            fallback["audits"][aid] = res.json()

        # Files
        res = await client.get(f"/v1/audits/{aid}/files", headers=headers)
        if res.status_code == 200:
            fallback["files"][aid] = res.json()

        # Privilege Map
        res = await client.get(f"/v1/audits/{aid}/privilege-map", headers=headers)
        if res.status_code == 200:
            fallback["privilege_maps"][aid] = res.json()

        # Findings
        res = await client.get(f"/v1/audits/{aid}/findings", headers=headers)
        if res.status_code == 200:
            fallback["findings"][aid] = res.json()
            items = res.json().get("items", [])
            for item in items:
                fid = item["id"]
                # Patches per finding
                p_res = await client.get(f"/v1/audits/{aid}/findings/{fid}/patches", headers=headers)
                if p_res.status_code == 200:
                    fallback["patches"][fid] = p_res.json()

        # Proofs
        res = await client.get(f"/v1/audits/{aid}/proofs", headers=headers)
        if res.status_code == 200:
            fallback["proofs"][aid] = res.json()

        # Invariants
        res = await client.get(f"/v1/audits/{aid}/invariants", headers=headers)
        if res.status_code == 200:
            fallback["invariants"][aid] = res.json()

    return fallback


if __name__ == "__main__":
    asyncio.run(main())

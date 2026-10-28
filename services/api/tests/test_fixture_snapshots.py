"""
Snapshot tests for all 10 fixtures under fixtures/contracts/:
  1. vault_basic
  2. token_accesscontrol
  3. custom_modifiers
  4. timelocked_admin
  5. capped_mint
  6. uups_proxy
  7. renounced_owner
  8. unguarded_admin
  9. inherited_guards
  10. assembly_edge

Compares the PrivilegeMap output against expected/privilege_map.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Audit, AuditFile
from auditor_core.privilege_map.analyzer import run_analyzing_stage, run_privilege_map_stage
from app.routers.privilege_map import _build_privilege_map_response

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"

FIXTURE_NAMES = [
    "vault_basic",
    "token_accesscontrol",
    "custom_modifiers",
    "timelocked_admin",
    "capped_mint",
    "uups_proxy",
    "renounced_owner",
    "unguarded_admin",
    "inherited_guards",
    "assembly_edge",
]


def _normalize_privilege_map(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes generated IDs so snapshot comparison is deterministic
    while asserting all substantive facts and scores match.
    """
    normalized = json.loads(json.dumps(data))
    for r in normalized.get("roles", []):
        for idx, act in enumerate(r.get("actions", [])):
            act["id"] = f"action_{idx}"
            if "span" in act:
                act["span"]["sha256"] = "normalized"
        for idx, bd in enumerate(r.get("breakdown", [])):
            bd["action_id"] = f"action_{idx}"
    return normalized


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
async def test_fixture_privilege_map_snapshot(
    fixture_name: str,
    db_session: AsyncSession,
) -> None:
    fix_dir = FIXTURES_DIR / fixture_name
    expected_file = fix_dir / "expected" / "privilege_map.json"
    assert expected_file.exists(), f"Snapshot file missing: {expected_file}"

    with open(expected_file, "r", encoding="utf-8") as ef:
        expected_raw = json.load(ef)

    sol_files = list(fix_dir.glob("*.sol"))
    assert len(sol_files) >= 1, f"No solidity files in {fix_dir}"
    sources = {f.name: f.read_text(encoding="utf-8") for f in sol_files}

    audit_id = uuid.uuid4()
    org_id = uuid.uuid4()

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    audit = Audit(
        id=audit_id,
        org_id=org_id,
        project_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        status="running",
        stage="analyzing",
        purge_after=now + timedelta(days=1),
    )
    db_session.add(audit)

    for path, code in sources.items():
        db_session.add(
            AuditFile(
                id=uuid.uuid4(),
                audit_id=audit_id,
                org_id=org_id,
                path=path,
                sha256="normalized",
                line_count=len(code.splitlines()),
                object_key="normalized",
            )
        )
    await db_session.commit()

    # Stage 2: Analyzing
    models, c_ids, not_an = await run_analyzing_stage(
        audit_id=audit_id,
        org_id=org_id,
        session=db_session,
        sources=sources,
        solc_version="0.8.24",
    )

    # Stage 3: Privilege Map
    pmap_res = await run_privilege_map_stage(
        audit_id=audit_id,
        org_id=org_id,
        session=db_session,
        contracts=models,
        contract_db_ids=c_ids,
    )

    # Build response
    resp = await _build_privilege_map_response(audit_id, org_id, db_session)

    actual_norm = _normalize_privilege_map(resp)
    expected_norm = _normalize_privilege_map(expected_raw)

    # Assert roles match
    assert len(actual_norm["roles"]) == len(expected_norm["roles"]), (
        f"Fixture {fixture_name} roles count mismatch"
    )

    for a_role, e_role in zip(actual_norm["roles"], expected_norm["roles"]):
        assert a_role["role_key"] == e_role["role_key"]
        assert a_role["blast_score"] == e_role["blast_score"]
        assert a_role["tier"] == e_role["tier"]
        assert a_role["worst_case"] == e_role["worst_case"]
        assert a_role["can_grant"] == e_role["can_grant"]
        assert len(a_role["actions"]) == len(e_role["actions"])
        for act_a, act_e in zip(a_role["actions"], e_role["actions"]):
            assert act_a["power_category"] == act_e["power_category"]
            assert act_a["score"] == act_e["score"]
            assert act_a["guard_roles"] == act_e["guard_roles"]
            assert act_a["mitigations"] == act_e["mitigations"]

    # Assert edges match
    assert actual_norm["edges"] == expected_norm["edges"]

    # Assert undetected notes match
    assert actual_norm["undetected_notes"] == expected_norm["undetected_notes"]

    # Assert scoring_config_version matches
    assert actual_norm["scoring_config_version"] == expected_norm["scoring_config_version"]


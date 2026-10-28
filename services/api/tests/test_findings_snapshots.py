"""
Snapshot tests for static findings across contract fixtures:
  - reentrancy_classic
  - unguarded_admin
  - vault_basic
  - token_accesscontrol
  - custom_modifiers
  - timelocked_admin
  - capped_mint
  - uups_proxy
  - renounced_owner
  - inherited_guards
  - assembly_edge
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
import pytest

from auditor_core.detectors.scanner import (
    run_slither_curated_scan,
    run_custom_detectors,
    deduplicate_and_filter_findings,
)
from auditor_core.privilege_map.semantic import build_semantic_models_for_project
from auditor_core.privilege_map.roles import resolve_roles_and_actions

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "contracts"

FIXTURE_NAMES = [
    "reentrancy_classic",
    "unguarded_admin",
    "vault_basic",
    "token_accesscontrol",
    "custom_modifiers",
    "timelocked_admin",
    "capped_mint",
    "uups_proxy",
    "renounced_owner",
    "inherited_guards",
    "assembly_edge",
]


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_findings_fixture_snapshot(fixture_name: str) -> None:
    fix_dir = FIXTURES_DIR / fixture_name
    expected_file = fix_dir / "expected" / "findings.json"
    assert expected_file.exists(), f"Missing findings snapshot: {expected_file}"

    with open(expected_file, "r", encoding="utf-8") as f:
        expected = json.load(f)

    sol_files = list(fix_dir.glob("*.sol"))
    assert len(sol_files) >= 1
    sources = {f.name: f.read_text(encoding="utf-8") for f in sol_files}

    slither_f = run_slither_curated_scan(sources, solc_version="0.8.24")
    models, _ = build_semantic_models_for_project(sources, solc_version="0.8.24")
    role_nodes, actions, missing_ac, notes = resolve_roles_and_actions(models, uuid.uuid4(), uuid.uuid4(), {}, {})
    custom_f = run_custom_detectors(models, missing_ac)
    all_f = deduplicate_and_filter_findings(slither_f + custom_f)

    findings_data = [
        {
            "title": f.title,
            "severity": f.severity,
            "source": f.source,
            "detector": f.detector,
            "scored": f.scored,
            "status": f.status,
            "start_line": f.start_line,
            "evidence_count": len(f.evidence),
            "evidence_kinds": [e.kind for e in f.evidence],
        }
        for f in all_f
    ]
    findings_data.sort(key=lambda x: (x["severity"], x["title"], x["start_line"]))

    assert findings_data == expected


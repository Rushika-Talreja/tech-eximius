"""
Template loader for Invariant Hunter Lite (Milestone 7).
Discovers and loads invariant templates from packages/auditor_core/invariants/templates/{category}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InvariantTemplate:
    id: str
    description: str
    applies_if: str
    category: str
    source_code: str


def get_templates_root() -> Path:
    """Find root directory containing invariant templates."""
    # Try package-local directory first
    curr = Path(__file__).resolve().parent
    local_tpl = curr / "templates"
    if local_tpl.exists():
        return local_tpl

    # Try packages/auditor_core/invariants/templates
    alt_tpl = curr.parent.parent / "invariants" / "templates"
    if alt_tpl.exists():
        return alt_tpl

    # Repo root fallback
    repo_root = curr.parent.parent.parent.parent
    repo_tpl = repo_root / "packages" / "auditor_core" / "invariants" / "templates"
    return repo_tpl


def load_invariant_templates(category: str | None = None) -> list[InvariantTemplate]:
    """Load templates for a given category (or all categories if None)."""
    root = get_templates_root()
    categories = [category] if category and category != "all" else ["erc20", "erc4626", "staking", "lending"]
    templates: list[InvariantTemplate] = []

    for cat in categories:
        cat_dir = root / cat
        meta_file = cat_dir / "metadata.json"
        if not meta_file.exists():
            continue

        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            continue

        for item in items:
            t_id = item["id"]
            t_desc = item["description"]
            t_applies = item["applies_if"]
            sol_name = item.get("file", f"{t_id}.sol")
            sol_path = cat_dir / sol_name

            source_code = ""
            if sol_path.exists():
                source_code = sol_path.read_text(encoding="utf-8")

            templates.append(
                InvariantTemplate(
                    id=t_id,
                    description=t_desc,
                    applies_if=t_applies,
                    category=cat,
                    source_code=source_code,
                )
            )

    return templates

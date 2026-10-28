"""
Pipeline Stage 1: Building.
Handles layout detection (Foundry, Hardhat, loose files), dependency fetching,
pragma analysis & solc version selection, sandbox compilation with solc standard-json,
and source manifest / audit_files generation.

Hard Rules:
- NEVER run user scripts, Hardhat tasks, postinstall scripts, or user tests.
- Compile in sandbox with NO network.
- On compilation failure: raise BUILD_FAILED with diagnostics (file, line, column, message).
  NEVER fall back to unverified review.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from auditor_core.sandbox.runner import SandboxRunner

logger = get_logger(__name__)

# Pinned toolchain defaults
PINNED_TOOLCHAIN = {
    "solc": "0.8.24",
    "slither": "0.10.2",
    "foundry": "0.2.0",
}


class BuildFailedError(Exception):
    """Raised when compilation fails with standard diagnostics."""

    def __init__(self, message: str, diagnostics: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.message = message
        self.diagnostics = diagnostics


@dataclass
class SourceFileEntry:
    path: str
    content: str
    sha256: str
    line_count: int
    is_dependency: bool


@dataclass
class BuildingResult:
    layout: str
    solc_version: str
    toolchain: dict[str, str]
    source_manifest: list[dict[str, Any]]
    audit_files: list[dict[str, Any]]
    analyzed_files: list[str]
    not_analyzed_files: list[dict[str, Any]]
    contracts: dict[str, Any]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def detect_layout(project_dir: Path) -> str:
    """Detect smart contract project layout."""
    if (project_dir / "foundry.toml").exists():
        return "foundry"
    for ext in ("js", "ts", "cjs", "mjs"):
        if (project_dir / f"hardhat.config.{ext}").exists():
            return "hardhat"
    return "loose"


def extract_pragma(content: str) -> str | None:
    """Extract pragma solidity version string from source code."""
    match = re.search(r"pragma\s+solidity\s+([^;]+);", content)
    return match.group(1).strip() if match else None


def locate_solc_binary(version: str) -> str:
    """Locate solc executable for a given version."""
    # 1. Check virtualenv solc-select artifacts
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        repo_root / ".venv" / ".solc-select" / "artifacts" / f"solc-{version}" / f"solc-{version}",
        Path(os.environ.get("VIRTUAL_ENV", "")) / ".solc-select" / "artifacts" / f"solc-{version}" / f"solc-{version}",
        Path.home() / ".solc-select" / "artifacts" / f"solc-{version}" / f"solc-{version}",
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)

    # 2. Check system PATH
    system_solc = shutil.which("solc")
    if system_solc:
        return system_solc

    # 3. Fallback: try default solc-0.8.24 artifact if available
    for c in candidates:
        default_candidate = c.parent.parent / "solc-0.8.24" / "solc-0.8.24"
        if default_candidate.exists():
            return str(default_candidate)

    return "solc"


def select_solc_version(
    sources: dict[str, str],
    requested_version: str | None = None,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """
    Select solc version and partition files.
    Returns: (chosen_version, compatible_file_paths, not_analyzed_entries)
    """
    installed_versions = ["0.8.24", "0.8.20", "0.7.6"]

    if requested_version and requested_version in installed_versions:
        chosen_version = requested_version
    else:
        chosen_version = "0.8.24"

    # Inspect pragma for each file
    compatible_files: list[str] = []
    not_analyzed: list[dict[str, Any]] = []

    for path, content in sources.items():
        pragma = extract_pragma(content)
        if not pragma:
            compatible_files.append(path)
            continue

        # Check basic compatibility
        if "0.7" in pragma and not chosen_version.startswith("0.7"):
            not_analyzed.append({
                "file": path,
                "reason": "incompatible_pragma",
                "pragma": pragma,
                "message": f"Pragma '{pragma}' incompatible with selected compiler '{chosen_version}'",
            })
        elif "0.8" in pragma and chosen_version.startswith("0.7"):
            not_analyzed.append({
                "file": path,
                "reason": "incompatible_pragma",
                "pragma": pragma,
                "message": f"Pragma '{pragma}' incompatible with selected compiler '{chosen_version}'",
            })
        else:
            compatible_files.append(path)

    # If all files were partitioned into not_analyzed, flip chosen_version
    if not compatible_files and not_analyzed:
        first_pragma = not_analyzed[0]["pragma"]
        if "0.7" in first_pragma:
            chosen_version = "0.7.6"
            compatible_files = [item["file"] for item in not_analyzed if "0.7" in item["pragma"]]
            not_analyzed = [item for item in not_analyzed if "0.7" not in item["pragma"]]

    return chosen_version, compatible_files, not_analyzed


def compile_with_solc(
    sources: dict[str, str],
    solc_version: str,
    sandbox_runner: SandboxRunner | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Compile solidity files using standard JSON interface inside the sandbox.
    Returns: (contracts_map, diagnostics)
    Raises: BuildFailedError on compilation errors.
    """
    solc_bin = locate_solc_binary(solc_version)
    runner = sandbox_runner or SandboxRunner(runtime="local")

    input_json = {
        "language": "Solidity",
        "sources": {path: {"content": content} for path, content in sources.items()},
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode", "evm.deployedBytecode", "metadata"],
                    "": ["ast"],
                }
            },
        },
    }

    cmd = [solc_bin, "--standard-json"]
    result = runner.run(
        cmd=cmd,
        input_data=json.dumps(input_json),
        allow_network=False,
    )

    if result.exit_code != 0 and not result.stdout:
        raise BuildFailedError(
            message=f"Compiler process exited with code {result.exit_code}",
            diagnostics=[{
                "file": "compiler",
                "line": 1,
                "column": 1,
                "message": result.stderr or "Compiler invocation failed",
                "severity": "error",
            }],
        )

    try:
        output = json.loads(result.stdout)
    except Exception as exc:
        raise BuildFailedError(
            message=f"Failed to parse compiler output: {exc}",
            diagnostics=[{
                "file": "compiler",
                "line": 1,
                "column": 1,
                "message": result.stdout[:500] if result.stdout else str(exc),
                "severity": "error",
            }],
        ) from exc

    raw_errors = output.get("errors", [])
    diagnostics: list[dict[str, Any]] = []
    has_fatal_error = False

    for err in raw_errors:
        severity = err.get("severity", "error")
        source_loc = err.get("sourceLocation") or {}
        file_name = source_loc.get("file", "unknown")
        start_offset = source_loc.get("start", 0)

        # Compute line and column from source content
        line_num = 1
        col_num = 1
        if file_name in sources and start_offset:
            prefix = sources[file_name][:start_offset]
            lines = prefix.split("\n")
            line_num = len(lines)
            col_num = len(lines[-1]) + 1

        diag = {
            "file": file_name,
            "line": line_num,
            "column": col_num,
            "message": err.get("message", "Compilation issue"),
            "severity": severity,
        }
        diagnostics.append(diag)
        if severity == "error":
            has_fatal_error = True

    if has_fatal_error:
        raise BuildFailedError(
            message="Compilation failed",
            diagnostics=[d for d in diagnostics if d["severity"] == "error"],
        )

    contracts = output.get("contracts", {})
    return contracts, diagnostics


def run_building_stage(
    upload_bytes: bytes,
    kind: str,
    options: dict[str, Any],
    org_id: str,
    audit_id: str,
    storage_client: Any,
) -> BuildingResult:
    """
    Execute complete Stage 1 Building logic.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Unpack upload safely
        sources: dict[str, str] = {}

        if kind == "sol":
            content = upload_bytes.decode("utf-8", errors="replace")
            path = "src/Contract.sol"
            sources[path] = content
            (tmp_path / "src").mkdir(parents=True, exist_ok=True)
            (tmp_path / path).write_text(content)
        elif kind == "zip":
            with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
                zf.extractall(tmp_path)

            # Discover all .sol files
            for root, _, files in os.walk(tmp_path):
                for f in files:
                    if f.endswith(".sol"):
                        full_path = Path(root) / f
                        rel_path = str(full_path.relative_to(tmp_path))
                        # Normalize path separators
                        rel_path = rel_path.replace("\\", "/")
                        sources[rel_path] = full_path.read_text(errors="replace")

        layout = detect_layout(tmp_path)
        logger.info("layout_detected", layout=layout, file_count=len(sources))

        # 2. Select solc version and check pragma compatibility
        requested_solc = options.get("solc_version")
        chosen_version, compatible_paths, not_analyzed = select_solc_version(
            sources, requested_version=requested_solc
        )

        compatible_sources = {k: sources[k] for k in compatible_paths}

        # 3. Compile within sandbox
        contracts, diagnostics = compile_with_solc(
            compatible_sources,
            solc_version=chosen_version,
        )

        # 4. Generate source manifest and store individual source files
        manifest: list[dict[str, Any]] = []
        audit_files_rows: list[dict[str, Any]] = []

        import uuid

        for rel_path, content in sources.items():
            content_bytes = content.encode("utf-8")
            sha256 = hashlib.sha256(content_bytes).hexdigest()
            line_count = len(content.splitlines())
            is_dep = rel_path.startswith("lib/") or rel_path.startswith("node_modules/")

            manifest.append({
                "path": rel_path,
                "sha256": sha256,
                "line_count": line_count,
                "is_dependency": is_dep,
            })

            # Store to S3/local storage: {org_id}/audits/{audit_id}/sources/{sha256}
            storage_key = f"{org_id}/audits/{audit_id}/sources/{sha256}"
            storage_client.put_object(
                key=storage_key,
                data=content_bytes,
                content_type="text/plain",
                metadata={"sha256": sha256, "path": rel_path},
            )

            audit_files_rows.append({
                "id": uuid.uuid4(),
                "path": rel_path,
                "sha256": sha256,
                "line_count": line_count,
                "is_dependency": is_dep,
                "object_key": storage_key,
            })

        toolchain = dict(PINNED_TOOLCHAIN)
        toolchain["solc"] = chosen_version

        analyzed_files = [f["path"] for f in manifest if not f["is_dependency"] and f["path"] in compatible_sources]

        return BuildingResult(
            layout=layout,
            solc_version=chosen_version,
            toolchain=toolchain,
            source_manifest=manifest,
            audit_files=audit_files_rows,
            analyzed_files=analyzed_files,
            not_analyzed_files=not_analyzed,
            contracts=contracts,
            diagnostics=diagnostics,
        )


"""
ContractSemanticModel extraction using Tree-sitter-solidity (exact spans) and Slither IR.
Extracts:
  - functions, modifiers and their bodies
  - state variables
  - inheritance
  - external calls
  - token flows (_mint, _burn, transfers, ETH sends)
  - upgradeability pattern (none, uups, transparent, beacon, diamond, unknown)
  - contract type (erc20, erc4626, staking, lending, other)
  - undetected notes (inline assembly, low-level calls, function pointers, proxies without implementation)
Graceful fallback to Tree-sitter-only if Slither fails.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import tree_sitter_solidity as tssolidity
from tree_sitter import Language, Parser

from app.logging_config import get_logger

logger = get_logger(__name__)

SOL_LANG = Language(tssolidity.language())


class CodeSpan(BaseModel):
    file: str
    start_line: int
    end_line: int
    sha256: str


class StateVariableSemantic(BaseModel):
    name: str
    type_name: str
    visibility: str = "internal"
    is_constant: bool = False
    is_immutable: bool = False


class ModifierSemantic(BaseModel):
    name: str
    parameters: list[dict[str, str]] = Field(default_factory=list)
    body_source: str = ""
    span: CodeSpan | None = None
    has_msg_sender_check: bool = False
    checked_variable: str | None = None
    is_mapping_check: bool = False
    role_checked: str | None = None


class FunctionSemantic(BaseModel):
    name: str
    signature: str
    contract_name: str
    visibility: str = "public"  # public, external, internal, private
    state_mutability: str = "nonpayable"  # pure, view, nonpayable, payable
    modifiers: list[str] = Field(default_factory=list)
    parameters: list[dict[str, str]] = Field(default_factory=list)
    span: CodeSpan
    body_source: str = ""
    state_writes: list[str] = Field(default_factory=list)
    state_reads: list[str] = Field(default_factory=list)
    external_calls: list[dict[str, Any]] = Field(default_factory=list)
    token_flows: list[dict[str, Any]] = Field(default_factory=list)
    has_selfdestruct: bool = False
    has_delegatecall: bool = False
    guard_roles: list[str] = Field(default_factory=list)
    guard_kind: str = "none"  # modifier, require_sender, role_check, none


class ContractSemanticModel(BaseModel):
    name: str
    kind: str = "contract"  # contract, library, interface, abstract
    contract_type: str = "other"  # erc20, erc4626, staking, lending, other
    upgradeability: str = "none"  # none, uups, transparent, beacon, diamond, unknown
    inheritance: list[str] = Field(default_factory=list)
    state_variables: list[StateVariableSemantic] = Field(default_factory=list)
    modifiers: list[ModifierSemantic] = Field(default_factory=list)
    functions: list[FunctionSemantic] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    undetected_notes: list[str] = Field(default_factory=list)


def classify_contract_type(function_names: set[str], inheritance: list[str]) -> str:
    """Classify contract into: erc20, erc4626, staking, lending, other."""
    inh_lower = [str(i).lower() for i in inheritance]

    if any("erc4626" in i for i in inh_lower) or {"asset", "totalAssets", "previewDeposit"}.issubset(function_names):
        return "erc4626"

    erc20_core = {"totalSupply", "balanceOf", "transfer", "transferFrom", "approve"}
    if any("erc20" in i for i in inh_lower) or len(erc20_core.intersection(function_names)) >= 3:
        return "erc20"

    staking_core = {"stake", "unstake", "claimReward", "getReward", "rewardRate"}
    if any("staking" in i for i in inh_lower) or len(staking_core.intersection(function_names)) >= 2:
        return "staking"

    lending_core = {"borrow", "repay", "liquidate", "borrowRate", "collateralFactor"}
    if any("lending" in i for i in inh_lower) or len(lending_core.intersection(function_names)) >= 2:
        return "lending"

    return "other"


def classify_upgradeability(
    contract_name: str,
    function_names: set[str],
    inheritance: list[str],
    source_code: str,
) -> str:
    """Classify upgradeability pattern: none, uups, transparent, beacon, diamond, unknown."""
    inh_lower = [str(i).lower() for i in inheritance]

    if any("uups" in i for i in inh_lower) or "_authorizeUpgrade" in function_names:
        return "uups"

    if any("transparent" in i for i in inh_lower) or "changeAdmin" in function_names or "ProxyAdmin" in source_code:
        return "transparent"

    if any("beacon" in i for i in inh_lower) or "upgradeBeacon" in function_names:
        return "beacon"

    if any("diamond" in i for i in inh_lower) or "diamondCut" in function_names:
        return "diamond"

    if "delegatecall" in source_code and "implementation" in source_code:
        return "unknown"

    return "none"


def extract_node_text(node: Any, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def parse_contract_tree_sitter(
    file_path: str,
    source_content: str,
) -> list[ContractSemanticModel]:
    """Extract semantic models per contract using Tree-sitter-solidity."""
    source_bytes = source_content.encode("utf-8")
    sha256_hash = hashlib.sha256(source_bytes).hexdigest()

    parser = Parser(SOL_LANG)
    tree = parser.parse(source_bytes)

    contracts: list[ContractSemanticModel] = []

    # Find top-level contract / interface / library declarations
    for node in tree.root_node.children:
        if node.type in ("contract_declaration", "interface_declaration", "library_declaration"):
            contract_model = _parse_contract_node(node, file_path, source_bytes, sha256_hash)
            if contract_model:
                contracts.append(contract_model)

    return contracts


def _parse_contract_node(
    contract_node: Any,
    file_path: str,
    source_bytes: bytes,
    sha256_hash: str,
) -> ContractSemanticModel | None:
    contract_name = ""
    kind = "contract"
    inheritance: list[str] = []
    modifiers: list[ModifierSemantic] = []
    functions: list[FunctionSemantic] = []
    state_variables: list[StateVariableSemantic] = []
    undetected_notes: list[str] = []

    if contract_node.type == "interface_declaration":
        kind = "interface"
    elif contract_node.type == "library_declaration":
        kind = "library"

    body_node = None
    for child in contract_node.children:
        if child.type == "identifier":
            contract_name = extract_node_text(child, source_bytes)
        elif child.type == "abstract":
            kind = "abstract"
        elif child.type == "inheritance_specifier":
            # Extracts base contract names
            text = extract_node_text(child, source_bytes)
            # Remove arguments if present, e.g. Ownable(msg.sender)
            base_names = [re.sub(r"\(.*?\)", "", part).strip() for part in text.split(",")]
            inheritance.extend([b for b in base_names if b])
        elif child.type == "contract_body":
            body_node = child

    if not contract_name or not body_node:
        return None

    # Parse contract body elements
    for member in body_node.children:
        if member.type == "state_variable_declaration":
            var_sem = _parse_state_var_node(member, source_bytes)
            if var_sem:
                state_variables.append(var_sem)
        elif member.type == "modifier_definition":
            mod_sem = _parse_modifier_node(member, file_path, source_bytes, sha256_hash)
            if mod_sem:
                modifiers.append(mod_sem)
        elif member.type == "function_definition":
            fn_sem = _parse_function_node(member, contract_name, file_path, source_bytes, sha256_hash)
            if fn_sem:
                functions.append(fn_sem)

    # Check for inline assembly and low-level calls in the contract
    def check_notes(n: Any) -> None:
        if "assembly" in n.type:
            line = n.start_point[0] + 1
            undetected_notes.append(f"Inline assembly at {file_path}:{line} not analyzed")
        elif n.type == "call_expression":
            expr_text = extract_node_text(n, source_bytes)
            if ".delegatecall" in expr_text or ".call{" in expr_text or ".call(" in expr_text:
                line = n.start_point[0] + 1
                undetected_notes.append(f"Low-level call (.call/.delegatecall) at {file_path}:{line} not analyzed")
        for ch in n.children:
            check_notes(ch)

    check_notes(contract_node)

    fn_names = {f.name for f in functions}
    contract_type = classify_contract_type(fn_names, inheritance)
    full_source = extract_node_text(contract_node, source_bytes)
    upgradeability = classify_upgradeability(contract_name, fn_names, inheritance, full_source)

    if upgradeability in ("uups", "transparent", "beacon") and "implementation" not in full_source.lower():
        undetected_notes.append(f"Proxy contract at {file_path} has no local implementation analyzed")

    return ContractSemanticModel(
        name=contract_name,
        kind=kind,
        contract_type=contract_type,
        upgradeability=upgradeability,
        inheritance=inheritance,
        state_variables=state_variables,
        modifiers=modifiers,
        functions=functions,
        roles=[],
        metadata={"spans": {"start_line": contract_node.start_point[0] + 1, "end_line": contract_node.end_point[0] + 1}},
        undetected_notes=undetected_notes,
    )


def _parse_state_var_node(node: Any, source_bytes: bytes) -> StateVariableSemantic | None:
    name = ""
    type_name = ""
    visibility = "internal"
    is_const = False
    is_immut = False

    for child in node.children:
        if child.type == "type_name":
            type_name = extract_node_text(child, source_bytes)
        elif child.type == "identifier":
            name = extract_node_text(child, source_bytes)
        elif child.type == "visibility":
            visibility = extract_node_text(child, source_bytes)
        elif child.type == "constant":
            is_const = True
        elif child.type == "immutable":
            is_immut = True

    if name:
        return StateVariableSemantic(
            name=name,
            type_name=type_name or "unknown",
            visibility=visibility,
            is_constant=is_const,
            is_immutable=is_immut,
        )

    text = extract_node_text(node, source_bytes)
    left = text.split("=")[0].replace(";", "").strip()
    parts = left.split()
    if len(parts) >= 2:
        name = parts[-1]
        type_name = parts[0]
        for v in ("public", "private", "internal"):
            if v in parts:
                visibility = v
                break
        is_const = "constant" in parts
        is_immut = "immutable" in parts
        return StateVariableSemantic(
            name=name,
            type_name=type_name,
            visibility=visibility,
            is_constant=is_const,
            is_immutable=is_immut,
        )
    return None


def _parse_modifier_node(node: Any, file_path: str, source_bytes: bytes, sha256_hash: str) -> ModifierSemantic | None:
    name = ""
    body_source = ""
    for child in node.children:
        if child.type == "identifier":
            name = extract_node_text(child, source_bytes)
        elif child.type == "function_body":
            body_source = extract_node_text(child, source_bytes)

    if not name:
        return None

    # Inspect body for access control checks
    has_sender_check = False
    checked_var = None
    is_mapping = False
    role_checked = None

    if "msg.sender" in body_source:
        has_sender_check = True
        match_eq = re.search(r"msg\.sender\s*==\s*([a-zA-Z0-9_]+)", body_source)
        if match_eq:
            checked_var = match_eq.group(1)
        match_map = re.search(r"([a-zA-Z0-9_]+)\s*\[\s*msg\.sender\s*\]", body_source)
        if match_map:
            checked_var = match_map.group(1)
            is_mapping = True

    match_role = re.search(r"hasRole\s*\(\s*([a-zA-Z0-9_]+)", body_source) or re.search(r"_checkRole\s*\(\s*([a-zA-Z0-9_]+)", body_source)
    if match_role:
        role_checked = match_role.group(1)

    span = CodeSpan(
        file=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        sha256=sha256_hash,
    )

    return ModifierSemantic(
        name=name,
        body_source=body_source,
        span=span,
        has_msg_sender_check=has_sender_check,
        checked_variable=checked_var,
        is_mapping_check=is_mapping,
        role_checked=role_checked,
    )


def _parse_function_node(
    node: Any,
    contract_name: str,
    file_path: str,
    source_bytes: bytes,
    sha256_hash: str,
) -> FunctionSemantic | None:
    name = ""
    visibility = "public"
    state_mutability = "nonpayable"
    modifiers: list[str] = []
    parameters: list[dict[str, str]] = []
    body_source = ""

    for child in node.children:
        if child.type == "identifier":
            name = extract_node_text(child, source_bytes)
        elif child.type == "visibility":
            visibility = extract_node_text(child, source_bytes)
        elif child.type == "state_mutability":
            state_mutability = extract_node_text(child, source_bytes)
        elif child.type == "modifier_invocation":
            mod_text = extract_node_text(child, source_bytes).strip()
            modifiers.append(mod_text)
        elif child.type == "parameter":
            param_text = extract_node_text(child, source_bytes)
            parts = param_text.split()
            if len(parts) >= 2:
                parameters.append({"type": parts[0], "name": parts[-1]})
            elif len(parts) == 1:
                parameters.append({"type": parts[0], "name": ""})
        elif child.type == "function_body":
            body_source = extract_node_text(child, source_bytes)

    if not name:
        # Fallback to constructor or fallback if applicable
        header_text = extract_node_text(node, source_bytes)
        if "constructor" in header_text:
            name = "constructor"
        elif "fallback" in header_text:
            name = "fallback"
        elif "receive" in header_text:
            name = "receive"
        else:
            name = "anonymous"

    # Build signature
    param_types = [p.get("type", "") for p in parameters]
    signature = f"{name}({','.join(param_types)})"

    span = CodeSpan(
        file=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        sha256=sha256_hash,
    )

    # Detect state writes, token flows, selfdestruct, delegatecall from body
    state_writes: list[str] = []
    token_flows: list[dict[str, Any]] = []
    has_selfdestruct = bool(re.search(r"\b(selfdestruct|suicide)\s*\(", body_source))
    has_delegatecall = bool(re.search(r"\.delegatecall\s*\(", body_source))

    if re.search(r"\b_mint\s*\(", body_source) or re.search(r"\b_safeMint\s*\(", body_source):
        token_flows.append({"kind": "mint"})
    if re.search(r"\b_burn\s*\(", body_source):
        token_flows.append({"kind": "burn"})
    if ".call{value:" in body_source or ".call{value :" in body_source or ".transfer(" in body_source:
        token_flows.append({"kind": "eth_send"})
    if re.search(r"\b(transfer|transferFrom|safeTransfer|safeTransferFrom)\s*\(", body_source):
        token_flows.append({"kind": "transfer"})

    # State writes detection from assignments
    assign_matches = re.findall(r"([a-zA-Z0-9_]+)\s*(?:=|\+=|-=|\*=)\s*[^;]+;", body_source)
    for m in assign_matches:
        if m not in ("bool", "uint", "uint256", "int", "address", "bytes32"):
            state_writes.append(m)

    return FunctionSemantic(
        name=name,
        signature=signature,
        contract_name=contract_name,
        visibility=visibility,
        state_mutability=state_mutability,
        modifiers=modifiers,
        parameters=parameters,
        span=span,
        body_source=body_source,
        state_writes=state_writes,
        state_reads=[],
        external_calls=[],
        token_flows=token_flows,
        has_selfdestruct=has_selfdestruct,
        has_delegatecall=has_delegatecall,
    )


def build_semantic_models_for_project(
    sources: dict[str, str],
    solc_version: str = "0.8.24",
) -> tuple[dict[str, ContractSemanticModel], list[dict[str, Any]]]:
    """
    Build ContractSemanticModel per contract for all project files.
    Attempts Slither IR enhancement; falls back to Tree-sitter-only on failure.
    Returns: (models_by_contract_name, not_analyzed_entries)
    """
    models: dict[str, ContractSemanticModel] = {}
    not_analyzed: list[dict[str, Any]] = []

    # 1. First extract all contracts via Tree-sitter
    for path, content in sources.items():
        try:
            parsed = parse_contract_tree_sitter(path, content)
            for m in parsed:
                models[m.name] = m
        except Exception as exc:
            logger.warning("treesitter_parse_failed", file=path, error=str(exc))
            not_analyzed.append({
                "file": path,
                "reason": "treesitter_parse_failed",
                "message": str(exc),
            })

    # 2. Try Slither IR enhancement if available
    try:
        from auditor_core.pipeline.building import locate_solc_binary
        solc_bin = locate_solc_binary(solc_version)

        # Ensure VIRTUAL_ENV is set for solc-select
        repo_root = Path(__file__).resolve().parents[4]
        venv_path = repo_root / ".venv"
        if venv_path.exists() and "VIRTUAL_ENV" not in os.environ:
            os.environ["VIRTUAL_ENV"] = str(venv_path)

        # Run Slither on sources
        # We can run Slither on individual contracts or directory
        from slither import Slither
        # For in-memory sources, write temporary files or check if file exists
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for rel_path, content in sources.items():
                target = tmp_path / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            # Run slither on each .sol file
            for rel_path in sources.keys():
                target = tmp_path / rel_path
                try:
                    slither_obj = Slither(str(target), solc=solc_bin)
                    for sc in slither_obj.contracts:
                        if sc.name in models:
                            m = models[sc.name]
                            # Enhance inheritance linearization from Slither IR
                            m.inheritance = [base.name for base in sc.inheritance if base.name != sc.name]
                            # Map Slither functions
                            for sf in sc.functions:
                                matching_fn = next((f for f in m.functions if f.name == sf.name), None)
                                if matching_fn:
                                    # State writes from Slither IR
                                    written = [v.name for v in sf.state_variables_written]
                                    matching_fn.state_writes = list(set(matching_fn.state_writes + written))
                                    read = [v.name for v in sf.state_variables_read]
                                    matching_fn.state_reads = list(set(matching_fn.state_reads + read))
                except Exception as file_exc:
                    logger.debug("slither_file_error", file=rel_path, error=str(file_exc))
    except Exception as exc:
        logger.info("slither_ir_degraded", error=str(exc))
        # Record limitation in coverage.not_analyzed
        for path in sources.keys():
            not_analyzed.append({
                "file": path,
                "reason": "slither_analysis_degraded",
                "message": f"Slither IR unavailable: {exc}. Tree-sitter AST used.",
            })

    return models, not_analyzed

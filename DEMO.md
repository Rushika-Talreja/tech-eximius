# DeFi Contract Auditor — 3-Minute Live Demo Script

This script walks through the end-to-end capabilities of the DeFi Contract Auditor in 3 minutes flat, using the pre-seeded demo environment.

---

## 0. Quick Start (< 15 seconds)

From the project root, run:
```bash
make demo
```
This automatically verifies the backend API and Next.js test console are active, seeds the three demo projects, and outputs the service URLs.

### Service URLs:
- **Test Console UI**: [http://localhost:3001](http://localhost:3001)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 1. Presenter Script (3 Minutes)

### 0:00 – 0:30 | Setup & Multi-Tenant Audit Overview
1. **Open the Test Console**: Navigate to [http://localhost:3001](http://localhost:3001).
2. **Navigate to Audits**: Click **Audits** in the navigation bar.
3. **Show Seeded Contracts**:
   - Point out the 3 pre-seeded demo contracts:
     1. `Demo: Yield Vault (Ownable)` — ID: `audit-vault-ownable`
     2. `Demo: Access Control Token` — ID: `audit-token-accesscontrol`
     3. `Demo: Classic Reentrancy` — ID: `audit-reentrancy-classic`
4. **Point to Audit Status**:
   - Each audit shows `status: completed`, execution logs, detected compiler version, and finding counts.
   - Note the permanent **Disclaimer Banner** at the top of the interface: *"Automated advisory prototype — not a certified security audit."*

---

### 0:30 – 1:30 | Privilege Map & Dynamic Blast Radius (Flagship Feature)
1. **Navigate to Privilege Map**: Click **Privilege Map** (or go to [http://localhost:3001/privilege-map?audit_id=audit-vault-ownable](http://localhost:3001/privilege-map?audit_id=audit-vault-ownable)).
2. **Inspect the Default Privilege Blast Radius**:
   - Under **Contract Role Privileges**, inspect the `OWNER` role on `SimpleVault`.
   - **Expected Output (Before Declaration)**:
     - **Role**: `OWNER`
     - **Blast Score**: `90`
     - **Severity Tier**: `CRITICAL` (Bright Red)
     - **Worst-Case Assessment**:
       > *"Owner can withdraw funds from SimpleVault with no delay. No timelock, no cap, no multisig assumed."*
     - **Privileged Capabilities**: Unbounded `withdrawAll()` and unbounded `mint()` with zero delay.
3. **Live Demonstration: Declare Decentralized Governance**:
   - Scroll down to the **Declare Role Governance** form.
   - Configure the following values:
     - **Role**: `OWNER`
     - **Governance Type**: Select `timelock_multisig` (or `multisig`)
     - **Threshold / Signers**: Set threshold to `3` of `5`
     - **Timelock Delay**: Set delay to `48` hours (`172800` seconds)
   - Click **Update Role Declaration**.
4. **Inspect the Updated Privilege Map**:
   - **Expected Output (After Declaration)**:
     - **Role**: `OWNER`
     - **Blast Score**: Drops from `90` down to `36`
     - **Severity Tier**: Shifts from `CRITICAL` to `MEDIUM` (Amber/Yellow)
     - **Updated Worst-Case Assessment**:
       > *"Owner can withdraw funds from SimpleVault with no delay. Declared: 3-of-5 multisig, 48h timelock."*
   - **Talking Point**: *"Instead of treating every privileged owner as an instant rugpull, our auditor mathematically adjusts risk based on verifiable governance constraints (multisig thresholds and timelock delays)."*

---

### 1:30 – 2:15 | Classic Reentrancy, Evidence Library & Exploit Proofs
1. **Switch Audit**: Enter `audit-reentrancy-classic` in the Audit ID field and click **Load**, or navigate to [http://localhost:3001/findings?audit_id=audit-reentrancy-classic](http://localhost:3001/findings?audit_id=audit-reentrancy-classic).
2. **Inspect Finding & Grounded Evidence**:
   - Observe the High finding: `Reentrancy in withdraw()`.
   - Expand the finding to reveal **Ground-Truth Evidence**:
     - Static AST taint analysis (state variable modified after external call).
     - Grounded incident context linked from our DeFi security corpus.
3. **Inspect the Foundry Exploit Proof**:
   - Click **Proofs & Invariants** (or go to [http://localhost:3001/proofs?audit_id=audit-reentrancy-classic](http://localhost:3001/proofs?audit_id=audit-reentrancy-classic)).
   - View the automated Foundry counterexample proof:
     - **Sandboxed Execution**: Executed in a hermetic container with network disabled and `ffi=false`.
     - **Proof Assertion**: Fails on the original contract (attacker successfully extracts balance), and passes on the verified patch.
4. **Inspect the Verified Patch**:
   - Click **Patches** (or go to [http://localhost:3001/patches?audit_id=audit-reentrancy-classic](http://localhost:3001/patches?audit_id=audit-reentrancy-classic)).
   - Point out the unified diff showing Checks-Effects-Interactions (CEI) state update reordering.
   - Status: `verified`, compiles cleanly, clears finding, passes tests.

---

### 2:15 – 3:00 | Honest Limitations & Safety Guarantees
Conclude the presentation by highlighting transparent limitations:

1. **Curated Evidence Library**:
   - The RAG knowledge base contains a focused set of documented DeFi vulnerability patterns and exploits. It does not claim full coverage of novel zero-days.
2. **Solidity Focus**:
   - Supports Solidity EVM contracts (solc 0.8.x). Vyper, Move, and Solana/Rust contracts are outside current scope.
3. **Research-Grade Advisory Prototype**:
   - The system is built to act as a force-multiplier for security researchers and protocol engineers, not as a replacement for comprehensive manual audit certifications.
4. **Reliability & Fallback Mode**:
   - If the backend or sandbox runner is unreachable during a live pitch, the test console features a **"Force Recorded Fallback"** toggle in the header navigation. When toggled, pre-generated snapshot data is served instantly, clearly marked with a prominent `[RECORDED]` badge to preserve complete transparency.

---

## 2. Resetting the Demo Environment

To wipe all audit data, reset the database, and restart from a clean slate:
```bash
make demo-reset
```
To bring the demo back up:
```bash
make demo
```


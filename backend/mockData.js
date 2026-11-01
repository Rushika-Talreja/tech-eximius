export const mockContractCode = `// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title YieldVault
 * @notice Automated vault allocating capital across DeFi yield strategies.
 * @dev Automated advisory check. Not a formal audit. Not legal advice.
 */
contract YieldVault {
    address public owner;
    address public emergencyGuardian;
    IERC20 public immutable asset;
    
    mapping(address => uint256) public balances;
    uint256 public totalVaultBalance;
    bool public paused;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event EmergencyDrain(address indexed caller, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "CALLER_NOT_OWNER");
        _;
    }

    modifier onlyGuardian() {
        require(msg.sender == emergencyGuardian, "CALLER_NOT_GUARDIAN");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "VAULT_PAUSED");
        _;
    }

    constructor(address _asset, address _guardian) {
        require(_asset != address(0), "INVALID_ASSET");
        asset = IERC20(_asset);
        owner = msg.sender;
        emergencyGuardian = _guardian;
    }

    function deposit(uint256 amount) external whenNotPaused {
        require(amount > 0, "INVALID_AMOUNT");
        asset.transferFrom(msg.sender, address(this), amount);
        balances[msg.sender] += amount;
        totalVaultBalance += amount;
        emit Deposited(msg.sender, amount);
    }

    // FINDING-082: Reentrancy vulnerability in withdrawal logic
    function withdraw(uint256 amount) external whenNotPaused {
        require(balances[msg.sender] >= amount, "INSUFFICIENT_BALANCE");
        
        // VULNERABLE: Interaction before state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "TRANSFER_FAILED");

        balances[msg.sender] -= amount;
        totalVaultBalance -= amount;
        emit Withdrawn(msg.sender, amount);
    }

    // FINDING-084: Unrestricted owner privileged drain
    function emergencyDrainVault(address recipient) external onlyOwner {
        uint256 currentBalance = asset.balanceOf(address(this));
        asset.transfer(recipient, currentBalance);
        emit EmergencyDrain(recipient, currentBalance);
    }

    function setEmergencyGuardian(address newGuardian) external onlyOwner {
        emergencyGuardian = newGuardian;
    }

    function setPaused(bool _paused) external onlyGuardian {
        paused = _paused;
    }
}
`;

export const mockAuditJob = {
  jobId: "AUD-2024-8841-B",
  status: "ACTIVE EXECUTION",
  contractName: "YieldVault.sol",
  sha256: "7f20e8b19a0c4f8287d19c3e981d7f6b901a8b273641de0912af90bc82aeda49",
  overallProgress: 71,
  estimatedRemainingSeconds: 14,
  elapsedSeconds: 32,
  sandboxLoad: 18,
  compilerPolicy: "SOLC 0.8.20 / SLITHER STATIC",
  targetContract: "YieldVault.sol",
  regulatoryFramework: "India: SEBI and RBI Direct Custody Annexure 4",
  analysisDepth: "Standard Static AST + Symbolic + Exploit DB",
  severityThreshold: "Critical and High",
  keyCustodyScheme: "Declared Multisig 2 of 3, 48h timelock enforced",
  oracleDependency: "Chainlink ETH/USD Feed (Staleness check required)",
  sandboxInstance: "sbx-802.us-east.advisory",
  currentStageIndex: 4,
  stages: [
    {
      index: 1,
      title: "Sandbox Initialization",
      desc: "Validating environment, seccomp filters, and isolated container execution boundaries.",
      status: "COMPLETED",
      latency: "1.2s"
    },
    {
      index: 2,
      title: "Solidity AST Compilation",
      desc: "Compiling via solc 0.8.20 and building normalized abstract syntax trees.",
      status: "COMPLETED",
      latency: "3.8s"
    },
    {
      index: 3,
      title: "Slither Static Taint Analysis",
      desc: "Evaluating data flow, uninitialized variables, and reentrancy vectors across call trees.",
      status: "COMPLETED",
      latency: "8.4s"
    },
    {
      index: 4,
      title: "Symbolic Execution & Path Exploration",
      desc: "Checking invariant reachability and constraint sat-solving via Z3/SMT engine.",
      status: "COMPLETED",
      latency: "18.6s"
    },
    {
      index: 5,
      title: "Privilege Boundary & Role Graphing",
      desc: "Mapping access-controlled methods, key holder topologies, and worst-case blast radiuses.",
      status: "ACTIVE",
      latency: "IN_PROGRESS"
    },
    {
      index: 6,
      title: "Invariant & State Property Verification",
      desc: "Checking balance conservation laws, math overflow/underflow, and flash-loan resistance.",
      status: "PENDING",
      latency: "--"
    },
    {
      index: 7,
      title: "Regulatory Compliance & Report Assembly",
      desc: "Aligning diagnostic evidence with advisory guidance and producing verifiable artifacts.",
      status: "PENDING",
      latency: "--"
    }
  ],
  telemetryLogs: [
    { time: "21:30:02.104", level: "INFO", message: "[SANDBOX] Container sbx-802 allocated with 2048MB memory limit." },
    { time: "21:30:03.310", level: "INFO", message: "[SOLC] Invoking compiler solc-v0.8.20 with optimizer runs=200." },
    { time: "21:30:07.112", level: "INFO", message: "[AST] Abstract syntax tree constructed: 4 contracts, 18 functions parsed." },
    { time: "21:30:08.520", level: "WARN", message: "[TAINT] Data flow taint detected at YieldVault.withdraw(uint256) -> msg.sender.call." },
    { time: "21:30:15.901", level: "INFO", message: "[Z3] Solving constraints for reentrant state reordering... SAT confirmed." },
    { time: "21:30:24.410", level: "WARN", message: "[PRIVILEGE] Method emergencyDrainVault has no timelock or cap; full balance reachable." },
    { time: "21:30:31.020", level: "INFO", message: "[RUNTIME] Memory pressure nominal (18%). Moving to stage 5 pipeline step." }
  ]
};

export const mockReportDashboard = {
  auditId: "AUD-2024-8841-B",
  contractName: "YieldVault.sol",
  timestamp: "2026-10-28 21:30 UTC",
  heuristicRiskScore: 78,
  riskTier: "HIGH ATTENTION REQUIRED",
  summaryStatement: "Heuristic evaluation identified 2 Critical and 2 High risk indicators. Reentrancy and unmitigated emergency drain require remediation prior to production deployment.",
  counts: {
    critical: 2,
    high: 2,
    medium: 1,
    low: 1,
    total: 6
  },
  privileges: [
    {
      role: "owner (Deployer)",
      powersGranted: "emergencyDrainVault(), setEmergencyGuardian()",
      riskScore: "9.4",
      riskLevel: "CRITICAL",
      worstCase: "Unilateral draining of total assets deposited in the vault.",
      keyCustody: "Assumed Single EOA Key (No Timelock Detected)"
    },
    {
      role: "emergencyGuardian",
      powersGranted: "setPaused(bool)",
      riskScore: "7.1",
      riskLevel: "HIGH",
      worstCase: "Indefinite denial of service by halting all deposit and withdrawal flows.",
      keyCustody: "Multisig 2 of 3 (Declared)"
    },
    {
      role: "strategist (Sub-role)",
      powersGranted: "adjustYieldWeights(), rebalance()",
      riskScore: "5.4",
      riskLevel: "MEDIUM",
      worstCase: "Suboptimal asset routing inducing impermanent loss or sandwiching.",
      keyCustody: "Smart Contract Automated Agent"
    },
    {
      role: "feeRecipient",
      powersGranted: "claimPerformanceFee()",
      riskScore: "2.3",
      riskLevel: "LOW",
      worstCase: "Premature fee accrual up to 2 percent hardcoded cap.",
      keyCustody: "Treasury Multisig"
    }
  ],
  findings: [
    {
      id: "FINDING-082",
      severity: "CRITICAL",
      title: "State Modification Following External Low-Level Call (Reentrancy)",
      location: "YieldVault.sol:58:9",
      method: "withdraw(uint256)",
      sourceType: "Static Taint + Z3 SAT",
      summary: "Balances mapping and totalVaultBalance are updated after the external call msg.sender.call{value: amount}(\"\"). A malicious recipient contract can reenter withdraw before balance update, draining the contract.",
      patchAvailable: true
    },
    {
      id: "FINDING-084",
      severity: "CRITICAL",
      title: "Unmitigated Direct Asset Extraction via emergencyDrainVault",
      location: "YieldVault.sol:68:5",
      method: "emergencyDrainVault(address)",
      sourceType: "Privilege Boundary Analysis",
      summary: "The owner key can unconditionally drain all tokens held by YieldVault in a single transaction without timelock, rate-limit, or multi-signature consensus requirement.",
      patchAvailable: false
    },
    {
      id: "FINDING-083",
      severity: "HIGH",
      title: "Unchecked Return Value in ERC20 transferFrom Invocation",
      location: "YieldVault.sol:49:9",
      method: "deposit(uint256)",
      sourceType: "Slither AST Detector",
      summary: "Non-standard ERC20 tokens that return false instead of reverting on transfer failure will cause internal balances to increment without token delivery.",
      patchAvailable: true
    },
    {
      id: "FINDING-085",
      severity: "HIGH",
      title: "Missing Staleness Check on External Price Oracle Round Data",
      location: "YieldVault.sol:84:13",
      method: "getLatestPrice()",
      sourceType: "Oracle Verification Pass",
      summary: "Chainlink latestRoundData return values updatedAt and answeredInRound are not validated against current block timestamp, permitting stale pricing attacks.",
      patchAvailable: true
    },
    {
      id: "FINDING-086",
      severity: "MEDIUM",
      title: "Absence of Minimum Output Slippage Bound on Liquidity Provision",
      location: "YieldVault.sol:112:5",
      method: "routeLiquidity(uint256)",
      sourceType: "DeFi Semantic Rule",
      summary: "Trade routing does not accept user-specified minAmountOut parameter, leaving transactions vulnerable to MEV sandwich bots in the mempool.",
      patchAvailable: false
    },
    {
      id: "FINDING-087",
      severity: "LOW",
      title: "Permissive Floating Pragma Declaration Across Module Files",
      location: "YieldVault.sol:2:1",
      method: "pragma solidity",
      sourceType: "Linter Standard Check",
      summary: "Contract uses pragma solidity 0.8.20 without locking patch revisions, risking compiler bug discrepancies during automated deployments.",
      patchAvailable: true
    }
  ],
  regulatoryAdvisories: [
    {
      authority: "SEBI Compliance Notice",
      clause: "Circular SEBI/HO/MIRSD/CR/2023/114",
      note: "Unilateral asset recovery functions that bypass multi-custodial safeguards fail self-custody certification standards."
    },
    {
      authority: "RBI Operational Resilience Advisory",
      clause: "Reserve Bank of India Risk Matrix Sec 12.B",
      note: "Smart contracts lacking automated circuit-breaker timelocks must classify admin keys under high-risk custodial exposure."
    }
  ],
  coverageStatement: {
    analyzedLines: 1420,
    suppressedLines: 18,
    outOfScopeLibraries: "OpenZeppelin Contracts v4.9.3 (Pre-verified)",
    solcVersion: "0.8.20",
    disclaimer: "Automated advisory check. Not a formal audit. Not legal advice."
  }
};

export const mockPatchDiff = {
  findingId: "FINDING-082",
  title: "Checks-Effects-Interactions & ReentrancyGuard Remediation",
  contractName: "YieldVault.sol",
  verificationStatus: {
    compiles: "PASS",
    findingCleared: "PASS",
    noNewFindings: "PASS",
    gasChange: "+2,140 gas (nonReentrant modifier overhead)"
  },
  rationale: "Remediation updates internal accounting balances prior to the external invocation and applies the OpenZeppelin nonReentrant guard to guarantee defense-in-depth.",
  diffLines: [
    { type: "context", lineNoOld: 53, lineNoNew: 53, text: "    // FINDING-082: Reentrancy vulnerability in withdrawal logic" },
    { type: "removed", lineNoOld: 54, lineNoNew: null, text: "    function withdraw(uint256 amount) external whenNotPaused {" },
    { type: "added", lineNoOld: null, lineNoNew: 54, text: "    function withdraw(uint256 amount) external whenNotPaused nonReentrant {" },
    { type: "context", lineNoOld: 55, lineNoNew: 55, text: "        require(balances[msg.sender] >= amount, \"INSUFFICIENT_BALANCE\");" },
    { type: "context", lineNoOld: 56, lineNoNew: 56, text: "        " },
    { type: "removed", lineNoOld: 57, lineNoNew: null, text: "        // VULNERABLE: Interaction before state update" },
    { type: "removed", lineNoOld: 58, lineNoNew: null, text: "        (bool success, ) = msg.sender.call{value: amount}(\"\");" },
    { type: "removed", lineNoOld: 59, lineNoNew: null, text: "        require(success, \"TRANSFER_FAILED\");" },
    { type: "removed", lineNoOld: 60, lineNoNew: null, text: "        balances[msg.sender] -= amount;" },
    { type: "removed", lineNoOld: 61, lineNoNew: null, text: "        totalVaultBalance -= amount;" },
    { type: "added", lineNoOld: null, lineNoNew: 57, text: "        // REMEDIATED: Effects applied before external interaction" },
    { type: "added", lineNoOld: null, lineNoNew: 58, text: "        balances[msg.sender] -= amount;" },
    { type: "added", lineNoOld: null, lineNoNew: 59, text: "        totalVaultBalance -= amount;" },
    { type: "added", lineNoOld: null, lineNoNew: 60, text: "        " },
    { type: "added", lineNoOld: null, lineNoNew: 61, text: "        (bool success, ) = msg.sender.call{value: amount}(\"\");" },
    { type: "added", lineNoOld: null, lineNoNew: 62, text: "        require(success, \"TRANSFER_FAILED\");" },
    { type: "context", lineNoOld: 62, lineNoNew: 63, text: "        emit Withdrawn(msg.sender, amount);" },
    { type: "context", lineNoOld: 63, lineNoNew: 64, text: "    }" }
  ]
};

export const mockEvidence = {
  findingId: "FINDING-082",
  title: "State Modification Following External Low-Level Call (Reentrancy)",
  severity: "CRITICAL",
  location: "YieldVault.sol:58:9",
  method: "withdraw(uint256)",
  sections: [
    {
      title: "Section 1: Why This Was Flagged",
      content: "Control flow graph analysis revealed that msg.sender.call transfers execution flow to an arbitrary address while contract storage balances[msg.sender] remains unmodified. The callee contract fallback routine can execute a second call to withdraw(), repeating the balance verification before the first reduction occurs."
    },
    {
      title: "Section 2: Evidence Type",
      content: "AST Trace & Control Flow Graph: Node 182 (CallExpr) -> Node 194 (StateVarWrite). CFG indicates path branching without lock verification."
    },
    {
      title: "Section 3: Historical Post-Mortems",
      content: "Parallels the Euler Finance protocol exploit ($197M lost) and Grim Finance vault drain ($30M lost), where external state sync delays enabled recursive collateralization calls."
    },
    {
      title: "Section 4: Regulatory Clause (SEBI & RBI Advisory Context)",
      content: "SEBI Circular 2023/114 Annexure B: Protocol architectures processing retail investor capital must enforce provable isolation against recursive reentrancy attacks."
    },
    {
      title: "Section 5: Confidence and Limits",
      content: "Static heuristic analysis confidence: 99.2%. Automated advisory check. Not a formal audit. Not legal advice."
    }
  ]
};


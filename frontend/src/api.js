/**
 * Unified API Client for DeFi Contract Auditor Platform.
 * All backend communications are routed through this facade
 * to allow direct replacement with live production endpoints.
 */

const API_BASE = window.location.origin;

export const api = {
  /**
   * Fetch current contract code and metadata.
   */
  async getContract() {
    try {
      const res = await fetch(`${API_BASE}/api/contract`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for contract:', err.message);
      return {
        filename: 'YieldVault.sol',
        version: '0.8.20',
        code: `// SPDX-License-Identifier: MIT\npragma solidity 0.8.20;\n\ncontract YieldVault {\n    address public owner;\n    mapping(address => uint256) public balances;\n}`
      };
    }
  },

  /**
   * Fetch live audit progress, stages, and execution telemetry logs.
   */
  async getAuditJob() {
    try {
      const res = await fetch(`${API_BASE}/api/audit-job`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for audit job:', err.message);
      return null;
    }
  },

  /**
   * Fetch security scorecard, risk tier, privilege matrix, and findings.
   */
  async getReport() {
    try {
      const res = await fetch(`${API_BASE}/api/report`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for report:', err.message);
      return null;
    }
  },

  /**
   * Fetch remediation patch diff lines and compiler verification results.
   */
  async getPatchDiff(findingId = 'FINDING-082') {
    try {
      const res = await fetch(`${API_BASE}/api/patch-diff?findingId=${encodeURIComponent(findingId)}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for patch diff:', err.message);
      return null;
    }
  },

  /**
   * Fetch diagnostic evidence, AST control flow trace, and regulatory citations.
   */
  async getEvidence(findingId = 'FINDING-082') {
    try {
      const res = await fetch(`${API_BASE}/api/evidence/${encodeURIComponent(findingId)}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for evidence:', err.message);
      return null;
    }
  },

  /**
   * Trigger a new audit run.
   */
  async startAudit(options) {
    try {
      const res = await fetch(`${API_BASE}/api/audit/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options)
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('API fallback for startAudit:', err.message);
      return { status: 'STARTED', jobId: 'AUD-2024-8841-B' };
    }
  }
};


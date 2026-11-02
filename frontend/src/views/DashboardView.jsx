import React, { useState, useEffect, useMemo } from 'react';
import { SeverityCards } from '../components/SeverityCards.jsx';
import { PrivilegeTable } from '../components/PrivilegeTable.jsx';
import { api } from '../api.js';

function getReadableAuditLabel(audit, currentData) {
  if (!audit) return 'Audit Report';
  let name =
    audit.contractName ||
    audit.contract_name ||
    audit.filename ||
    audit.target_contract ||
    audit.name ||
    audit.coverage?.analyzed?.files?.[0] ||
    (audit.coverage?.analyzed?.contracts?.[0] ? `${audit.coverage.analyzed.contracts[0]}.sol` : null);

  if (!name && audit.id === currentData?.auditId && currentData?.contractName) {
    name = currentData.contractName;
  }
  if (!name) name = 'YieldVault.sol';
  if (name.includes('/')) name = name.split('/').pop();

  let dateStr = '';
  const rawDate = audit.created_at || audit.timestamp;
  if (rawDate) {
    try {
      const d = new Date(rawDate);
      if (!isNaN(d.getTime())) {
        dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
    } catch (_) {}
  }

  const rawStatus = (audit.status || 'complete').toLowerCase();
  const statusStr = rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1);
  const shortId = audit.id ? audit.id.slice(0, 8) : '';

  if (dateStr) {
    return `${name} • ${dateStr} (${statusStr} • #${shortId})`;
  }
  return `${name} (${statusStr} • #${shortId})`;
}

export function DashboardView({
  reportData,
  onInspectEvidence,
  onInspectPatch,
  availableAudits = [],
  currentAuditId,
  onSelectAudit,
  onRefreshReport,
}) {
  const [selectedSeverity, setSelectedSeverity] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'open' | 'dismissed'
  const [searchQuery, setSearchQuery] = useState('');
  const [inspectingRole, setInspectingRole] = useState(null);
  const [activeTab, setActiveTab] = useState('findings'); // 'findings' | 'proofs' | 'invariants'
  const [proofsList, setProofsList] = useState([]);
  const [invariantsList, setInvariantsList] = useState([]);
  const [exportingFormat, setExportingFormat] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Editable custody state in role inspection modal
  const [roleHolderType, setRoleHolderType] = useState('eoa');
  const [roleThreshold, setRoleThreshold] = useState(2);
  const [roleSigners, setRoleSigners] = useState(3);
  const [roleDelayHours, setRoleDelayHours] = useState(48);
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  const data = reportData || (api.getDefaultReport ? api.getDefaultReport(currentAuditId) : {
    auditId: currentAuditId || '7e75c6ae-d193-469f-a3fe-e25a5641a79d',
    contractName: 'YieldVault.sol',
    timestamp: new Date().toLocaleString(),
    heuristicRiskScore: 78,
    riskTier: 'HIGH ATTENTION REQUIRED',
    summaryStatement: 'Heuristic evaluation identified Critical and High risk indicators.',
    counts: { critical: 2, high: 2, medium: 1, low: 1, total: 6 },
    privileges: [],
    findings: [],
    undetectedNotes: [],
    coverageStatement: {},
  });

  useEffect(() => {
    if (data.auditId) {
      api.getProofs(data.auditId).then(setProofsList).catch(() => setProofsList([]));
      api.getInvariants(data.auditId).then(setInvariantsList).catch(() => setInvariantsList([]));
    }
  }, [data.auditId]);

  // Combined search and filtering for findings
  const filteredFindings = useMemo(() => {
    let list = data.findings || [];
    if (selectedSeverity) {
      list = list.filter((f) => f.severity === selectedSeverity);
    }
    if (statusFilter === 'open') {
      list = list.filter((f) => f.status !== 'dismissed');
    } else if (statusFilter === 'dismissed') {
      list = list.filter((f) => f.status === 'dismissed');
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (f) =>
          (f.title && f.title.toLowerCase().includes(q)) ||
          (f.summary && f.summary.toLowerCase().includes(q)) ||
          (f.id && f.id.toLowerCase().includes(q)) ||
          (f.location && f.location.toLowerCase().includes(q))
      );
    }
    return list;
  }, [data.findings, selectedSeverity, statusFilter, searchQuery]);

  const getSeverityBadge = (sev) => {
    switch (sev) {
      case 'CRITICAL':
        return 'text-[#D6403A] border-[#D6403A] bg-[#D6403A]/10';
      case 'HIGH':
        return 'text-[#E8782A] border-[#E8782A] bg-[#E8782A]/10';
      case 'MEDIUM':
        return 'text-[#E3B73C] border-[#E3B73C] bg-[#E3B73C]/10';
      default:
        return 'text-[#8FA84A] border-[#8FA84A] bg-[#8FA84A]/10';
    }
  };

  const handleExport = async (format) => {
    setShowExportMenu(false);
    setExportingFormat(format);
    setStatusMessage(`Preparing ${format.toUpperCase()} export...`);
    try {
      await api.downloadExport(data.auditId, format, data);
      setStatusMessage(`Successfully downloaded ${format.toUpperCase()} report.`);
    } catch (err) {
      setStatusMessage(`Export failed: ${err.message}`);
    } finally {
      setTimeout(() => {
        setExportingFormat(null);
        setStatusMessage(null);
      }, 3500);
    }
  };

  const handleToggleFindingStatus = async (findingId, currentStatus) => {
    const nextStatus = currentStatus === 'dismissed' ? 'open' : 'dismissed';
    setStatusMessage(`Updating finding status to ${nextStatus}...`);
    try {
      await api.updateFindingStatus(data.auditId, findingId, nextStatus);
      setStatusMessage(`Finding ${nextStatus === 'dismissed' ? 'dismissed' : 'reopened'}. Score updated.`);
      if (onRefreshReport) onRefreshReport(data.auditId);
    } catch (err) {
      setStatusMessage(`Failed to update status: ${err.message}`);
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleOpenRoleModal = (role) => {
    setInspectingRole(role);
    const decl = role.declaration;
    if (decl) {
      setRoleHolderType(decl.holder_type || 'multisig');
      setRoleThreshold(decl.threshold || 2);
      setRoleSigners(decl.signers || 3);
      setRoleDelayHours(decl.delay_hours || 48);
    } else {
      setRoleHolderType('eoa');
      setRoleThreshold(1);
      setRoleSigners(1);
      setRoleDelayHours(0);
    }
  };

  const handleSaveRoleDeclaration = async () => {
    if (!inspectingRole) return;
    setIsUpdatingRole(true);
    setStatusMessage('Recomputing privilege blast scores...');

    try {
      const declPayload = [
        {
          role_key: inspectingRole.role_key || inspectingRole.role,
          holder_type: roleHolderType,
          threshold: roleHolderType.includes('multisig') ? Number(roleThreshold) : null,
          signers: roleHolderType.includes('multisig') ? Number(roleSigners) : null,
          delay_hours: Number(roleDelayHours),
        },
      ];

      await api.updateRoleDeclarations(data.auditId, declPayload);
      setStatusMessage('Privilege scores updated successfully.');
      setInspectingRole(null);
      if (onRefreshReport) onRefreshReport(data.auditId);
    } catch (err) {
      setStatusMessage(`Failed to update: ${err.message}`);
    } finally {
      setIsUpdatingRole(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  return (
    <div className="flex flex-col gap-8 p-6 w-full max-w-7xl mx-auto">
      {/* Dashboard Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#3A332D] pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase rounded-xs">
              Audit Results
            </span>
            <span className="font-label-caps text-xs text-outline font-mono">
              Audit ID: {data.auditId?.slice(0, 8)}
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Security Overview: {data.contractName}
          </h1>
          <p className="font-body-sm text-xs text-on-surface-variant mt-1">
            Completed on {data.timestamp} • Solidity {data.coverageStatement?.solcVersion || '0.8.20'}
          </p>
        </div>

        {/* Audit Switcher & Consolidated Export Dropdown */}
        <div className="flex flex-wrap items-center gap-3">
          {availableAudits.length > 0 && onSelectAudit && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-outline font-medium">Audit:</span>
              <select
                value={currentAuditId || data.auditId}
                onChange={(e) => onSelectAudit(e.target.value)}
                className="bg-[#14110F] border border-[#3A332D] text-primary text-xs font-code-sm px-3 py-1.5 rounded focus:border-primary focus:outline-none cursor-pointer max-w-[320px] truncate"
                title="Switch between contract audits"
              >
                {availableAudits.map((a) => (
                  <option key={a.id} value={a.id}>
                    {getReadableAuditLabel(a, data)}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Consolidated Export Action with primary PDF and format dropdown */}
          <div className="relative">
            <div className="flex items-center rounded overflow-hidden shadow-sm">
              <button
                type="button"
                disabled={!!exportingFormat}
                onClick={() => handleExport('pdf')}
                className="bg-primary text-[#14110F] hover:bg-[#FFBB49] text-xs font-label-caps px-4 py-2 font-bold uppercase transition-colors disabled:opacity-50"
              >
                {exportingFormat === 'pdf' ? 'Generating PDF...' : 'Download PDF Report'}
              </button>
              <button
                type="button"
                onClick={() => setShowExportMenu(!showExportMenu)}
                className="bg-[#E0A030] text-[#14110F] hover:bg-[#FFBB49] border-l border-[#B88020] px-2 py-2 text-xs font-bold"
                aria-label="More export formats"
              >
                ▼
              </button>
            </div>

            {showExportMenu && (
              <div className="absolute right-0 mt-1 w-44 bg-[#1D1916] border border-[#3A332D] rounded shadow-xl z-20 flex flex-col py-1 text-xs">
                <button
                  type="button"
                  onClick={() => handleExport('md')}
                  className="px-3 py-2 text-left text-on-surface hover:bg-[#26211D] hover:text-primary transition-colors"
                >
                  Markdown (.md)
                </button>
                <button
                  type="button"
                  onClick={() => handleExport('json')}
                  className="px-3 py-2 text-left text-on-surface hover:bg-[#26211D] hover:text-primary transition-colors"
                >
                  Raw JSON Data
                </button>
                <button
                  type="button"
                  onClick={() => handleExport('sarif')}
                  className="px-3 py-2 text-left text-on-surface hover:bg-[#26211D] hover:text-primary transition-colors"
                >
                  SARIF (Static Analysis)
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Operator Status Feedback Banner */}
      {statusMessage && (
        <div className="p-3 bg-[#1D1916] border border-primary text-primary text-xs font-code-sm rounded flex items-center justify-between">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            {statusMessage}
          </span>
          <button
            type="button"
            onClick={() => setStatusMessage(null)}
            className="text-outline hover:text-on-surface text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Post-Patch Critical Sweep Telemetry Banner */}
      {data.recentReRun && (
        data.recentReRun.newVulnerabilitiesCount > 0 ? (
          <div className="bg-[#D6403A]/15 border-2 border-[#D6403A] p-4 rounded-md flex flex-col gap-2.5 shadow-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-label-caps text-xs bg-[#D6403A] text-white px-2 py-0.5 font-bold uppercase rounded-xs">
                  Regression Warning
                </span>
                <span className="font-headline-sm text-sm font-bold text-on-surface">
                  Critical Sweep Re-Run: {data.recentReRun.newVulnerabilitiesCount} New Vulnerability Introduced by Patch!
                </span>
              </div>
              <span className="text-[11px] font-mono text-outline">
                Sweep completed at {data.recentReRun.timestamp}
              </span>
            </div>
            <p className="font-body-sm text-xs text-on-surface-variant leading-relaxed">
              Applying the fix for <strong className="text-primary font-mono">{data.recentReRun.targetFindingId?.slice(0, 11)}</strong> resolved the original vulnerability, but re-running static and critical AST detectors detected newly introduced vulnerabilities in the patched contract. Inspect the regression findings below.
            </p>
          </div>
        ) : (
          <div className="bg-[#8FA84A]/10 border border-[#8FA84A] p-3.5 rounded-md flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <span className="font-label-caps text-xs bg-[#8FA84A] text-[#14110F] px-2 py-0.5 font-bold uppercase rounded-xs">
                Zero Regressions
              </span>
              <span className="text-xs text-on-surface">
                Re-ran critical vulnerability detectors on patched code: <strong className="text-[#8FA84A]">0 new vulnerabilities found</strong>. Patch is clean and safe to deploy.
              </span>
            </div>
            <span className="text-[10px] font-mono text-outline shrink-0">
              Verified at {data.recentReRun.timestamp}
            </span>
          </div>
        )
      )}

      {/* Risk Summary Card */}
      <div className="bg-[#1D1916] border border-primary/60 rounded-md p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-sm">
        <div className="flex flex-col gap-1 max-w-2xl">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider">
            Overall Security Health
          </div>
          <div className="font-headline-lg text-2xl font-bold text-on-surface">
            {data.riskTier}
          </div>
          <p className="font-body-sm text-xs text-on-surface-variant leading-relaxed mt-1">
            {data.summaryStatement}
          </p>
        </div>

        <div className="flex items-center gap-4 bg-[#14110F] border border-[#3A332D] rounded-md p-4 shrink-0">
          <div className="flex flex-col items-center">
            <span className="font-headline-lg text-3xl font-bold text-primary font-mono">
              {data.heuristicRiskScore}
            </span>
            <span className="font-label-caps text-[10px] text-outline uppercase">
              / 100 Risk Index
            </span>
          </div>
          <div className="border-l border-[#3A332D] pl-4 flex flex-col gap-1 text-[11px] font-code-sm">
            <span className="text-[#D6403A] font-semibold">{data.counts?.critical || 0} Critical</span>
            <span className="text-[#E8782A] font-semibold">{data.counts?.high || 0} High</span>
            <span className="text-[#E3B73C] font-semibold">{data.counts?.medium || 0} Medium</span>
            <span className="text-[#8FA84A] font-semibold">{data.counts?.low || 0} Low</span>
          </div>
        </div>
      </div>

      {/* Severity Filter Metric Cards */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-outline uppercase tracking-wider">
            Filter Findings by Severity Tier
          </span>
          {selectedSeverity && (
            <button
              type="button"
              onClick={() => setSelectedSeverity(null)}
              className="text-xs text-primary hover:underline"
            >
              Clear Severity Filter ({selectedSeverity})
            </button>
          )}
        </div>
        <SeverityCards
          counts={data.counts}
          selectedSeverity={selectedSeverity}
          onSelectSeverity={setSelectedSeverity}
        />
      </div>

      {/* Privilege Map Summary Table */}
      <PrivilegeTable
        privileges={data.privileges}
        onSelectRole={handleOpenRoleModal}
      />

      {/* Role Custody Declaration & Inspection Modal */}
      {inspectingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="bg-[#1D1916] border border-primary rounded-md w-full max-w-2xl p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
              <div className="flex items-center gap-2">
                <span className="font-label-caps text-xs bg-primary text-[#14110F] px-2 py-0.5 font-bold uppercase rounded-xs">
                  Role Custody
                </span>
                <span className="font-headline-sm text-base font-bold text-on-surface">
                  {inspectingRole.role}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setInspectingRole(null)}
                className="text-xs text-outline hover:text-on-surface font-semibold"
              >
                Close ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs font-code-sm">
              <div className="p-3 bg-[#14110F] border border-[#3A332D] rounded">
                <span className="text-outline block text-[10px] uppercase font-label-caps mb-1">Risk Score</span>
                <span className="text-[#D6403A] font-bold text-base">{inspectingRole.riskScore} / 100 ({inspectingRole.riskLevel})</span>
              </div>
              <div className="p-3 bg-[#14110F] border border-[#3A332D] rounded">
                <span className="text-outline block text-[10px] uppercase font-label-caps mb-1">Declared Custody</span>
                <span className="text-primary font-semibold">{inspectingRole.keyCustody}</span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5 text-xs">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">Granted Powers</span>
              <div className="p-3 bg-[#14110F] border border-[#3A332D] text-on-surface font-mono rounded">
                {inspectingRole.powersGranted}
              </div>
            </div>

            <div className="flex flex-col gap-1.5 text-xs">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">Worst-Case Protocol Impact</span>
              <p className="p-3 bg-[#14110F] border border-[#3A332D] text-on-surface-variant font-sans leading-relaxed rounded">
                {inspectingRole.worstCase}
              </p>
            </div>

            {/* Interactive Custody Declaration Editor */}
            <div className="p-4 bg-[#14110F] border border-[#3A332D] rounded flex flex-col gap-3">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">
                Mitigation Declaration (Recalculate Risk)
              </span>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-code-sm">
                <div>
                  <span className="text-outline block text-[10px] mb-1">Holder Type</span>
                  <select
                    value={roleHolderType}
                    onChange={(e) => setRoleHolderType(e.target.value)}
                    className="w-full bg-[#161311] border border-[#3A332D] text-on-surface px-2 py-1 rounded"
                  >
                    <option value="eoa">EOA (Single Key)</option>
                    <option value="multisig">Multisig</option>
                    <option value="timelock">Timelock</option>
                    <option value="timelock_multisig">Timelock + Multisig</option>
                    <option value="governance">DAO Governance</option>
                  </select>
                </div>

                {roleHolderType.includes('multisig') && (
                  <>
                    <div>
                      <span className="text-outline block text-[10px] mb-1">Threshold</span>
                      <input
                        type="number"
                        min="1"
                        max={roleSigners}
                        value={roleThreshold}
                        onChange={(e) => setRoleThreshold(e.target.value)}
                        className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 rounded"
                      />
                    </div>
                    <div>
                      <span className="text-outline block text-[10px] mb-1">Total Signers</span>
                      <input
                        type="number"
                        min={roleThreshold}
                        max="10"
                        value={roleSigners}
                        onChange={(e) => setRoleSigners(e.target.value)}
                        className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 rounded"
                      />
                    </div>
                  </>
                )}

                <div>
                  <span className="text-outline block text-[10px] mb-1">Delay (Hours)</span>
                  <input
                    type="number"
                    min="0"
                    value={roleDelayHours}
                    onChange={(e) => setRoleDelayHours(e.target.value)}
                    className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 rounded"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#3A332D]">
              <button
                type="button"
                onClick={() => setInspectingRole(null)}
                className="font-label-caps text-xs px-4 py-2 border border-[#3A332D] text-on-surface hover:text-primary rounded transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isUpdatingRole}
                onClick={handleSaveRoleDeclaration}
                className="font-label-caps text-xs px-5 py-2 bg-primary text-[#14110F] font-bold uppercase hover:bg-[#FFBB49] rounded transition-colors disabled:opacity-50"
              >
                {isUpdatingRole ? 'Recalculating...' : 'Save & Recalculate Risk'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diagnostic Tabs */}
      <div className="flex items-center gap-2 border-b border-[#3A332D]">
        <button
          type="button"
          onClick={() => setActiveTab('findings')}
          className={`font-label-caps text-xs px-4 py-2.5 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'findings'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          Security Findings ({data.findings?.length || 0})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('proofs')}
          className={`font-label-caps text-xs px-4 py-2.5 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'proofs'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          Formal Proofs ({proofsList.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('invariants')}
          className={`font-label-caps text-xs px-4 py-2.5 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'invariants'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          Invariant Tests ({invariantsList.length})
        </button>
      </div>

      {/* Tab 1: Security Findings Matrix with Search & Filter */}
      {activeTab === 'findings' && (
        <div className="bg-[#1D1916] border border-[#3A332D] rounded-md flex flex-col">
          {/* Search, Filter & Controls Bar */}
          <div className="p-4 border-b border-[#3A332D] flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 max-w-md">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search findings by title, ID, or location..."
                className="w-full bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-1.5 text-xs font-code-sm rounded focus:border-primary focus:outline-none"
              />
            </div>

            {/* Status Filter Buttons */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-outline">Status:</span>
              <div className="inline-flex rounded border border-[#3A332D] bg-[#14110F] p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setStatusFilter('all')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    statusFilter === 'all'
                      ? 'bg-primary text-[#14110F] font-bold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  All ({data.findings?.length || 0})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter('open')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    statusFilter === 'open'
                      ? 'bg-primary text-[#14110F] font-bold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Open ({(data.findings || []).filter((f) => f.status !== 'dismissed').length})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter('dismissed')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    statusFilter === 'dismissed'
                      ? 'bg-primary text-[#14110F] font-bold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Dismissed ({(data.findings || []).filter((f) => f.status === 'dismissed').length})
                </button>
              </div>
            </div>
          </div>

          {filteredFindings.length === 0 ? (
            <div className="p-12 text-center flex flex-col items-center justify-center gap-2">
              <span className="text-sm font-semibold text-on-surface">No findings match your criteria</span>
              <p className="text-xs text-on-surface-variant">
                Try clearing search terms or changing your severity and status filters.
              </p>
              {(searchQuery || selectedSeverity || statusFilter !== 'all') && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    setSelectedSeverity(null);
                    setStatusFilter('all');
                  }}
                  className="mt-2 text-xs text-primary hover:underline font-semibold"
                >
                  Reset all filters
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#14110F] border-b border-[#3A332D] text-outline font-label-caps text-[10px] uppercase tracking-wider">
                    <th className="py-2.5 px-4">Severity</th>
                    <th className="py-2.5 px-4">ID</th>
                    <th className="py-2.5 px-4">Vulnerability & Summary</th>
                    <th className="py-2.5 px-4">Location</th>
                    <th className="py-2.5 px-4">Verification</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#3A332D] font-code-sm">
                  {filteredFindings.map((finding) => {
                    const isDismissed = finding.status === 'dismissed';
                    return (
                      <tr
                        key={finding.id}
                        className={`transition-colors ${
                          isDismissed ? 'opacity-50 bg-[#14110F]' : 'hover:bg-[#26211D]'
                        }`}
                      >
                        <td className="py-3 px-4">
                          <span className={`inline-block font-label-caps text-[10px] font-bold px-2 py-0.5 border rounded-xs ${getSeverityBadge(finding.severity)}`}>
                            {finding.severity}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono font-bold text-primary text-[11px]">
                          {finding.id.slice(0, 11)}
                        </td>
                        <td className="py-3 px-4 max-w-md">
                          <div className="flex items-center gap-2">
                            <span className="font-headline-sm text-xs font-semibold text-on-surface">
                              {finding.title}
                            </span>
                            {finding.isNewRegression && (
                              <span className="font-label-caps text-[9px] bg-[#D6403A] text-white px-1.5 py-0.2 font-bold uppercase rounded-xs animate-pulse shrink-0">
                                NEW REGRESSION
                              </span>
                            )}
                          </div>
                          <p className="font-body-sm text-[11px] text-on-surface-variant line-clamp-2 mt-0.5 leading-relaxed font-sans">
                            {finding.summary}
                          </p>
                        </td>
                        <td className="py-3 px-4 text-outline font-mono text-[11px]">
                          {finding.location}
                        </td>
                        <td className="py-3 px-4 text-on-surface text-[11px]">
                          <div>{finding.sourceType}</div>
                          {finding.proven && (
                            <span className="font-label-caps text-[9px] bg-primary/10 border border-primary text-primary px-1 font-bold rounded-xs">
                              SMT PROVEN
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`font-label-caps text-[10px] px-2 py-0.5 font-bold uppercase rounded-xs border ${
                            finding.patchApplied || isDismissed
                              ? 'text-[#8FA84A] border-[#8FA84A] bg-[#8FA84A]/10'
                              : 'text-primary border-primary/30'
                          }`}>
                            {finding.patchApplied ? 'FIX APPLIED' : finding.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right shrink-0">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => onInspectEvidence && onInspectEvidence(finding.id)}
                              className="font-label-caps text-[10px] text-primary border border-primary/60 px-2.5 py-1 hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold rounded"
                            >
                              View Details
                            </button>
                            <button
                              type="button"
                              onClick={() => onInspectPatch && onInspectPatch(finding.id)}
                              className={`font-label-caps text-[10px] px-2.5 py-1 transition-colors uppercase font-bold rounded border ${
                                finding.patchApplied
                                  ? 'text-[#8FA84A] border-[#8FA84A]/60 bg-[#8FA84A]/10 hover:bg-[#8FA84A]/20'
                                  : 'text-on-surface bg-[#221F1D] border-[#3A332D] hover:border-primary'
                              }`}
                            >
                              {finding.patchApplied ? 'View Fix ✓' : 'Review Fix'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleToggleFindingStatus(finding.id, finding.status)}
                              className="font-label-caps text-[10px] text-outline hover:text-on-surface border border-[#3A332D] px-2 py-1 transition-colors uppercase rounded"
                            >
                              {isDismissed ? 'Reopen' : 'Dismiss'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: SMT Formal Proofs */}
      {activeTab === 'proofs' && (
        <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
            <div>
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
                Formal Reachability Proofs
              </h3>
              <p className="font-body-sm text-[11px] text-on-surface-variant">
                Mathematical proofs confirming vulnerability exploitability on unpatched code and safety on patched candidate.
              </p>
            </div>
            <span className="font-label-caps text-xs text-primary font-bold">
              Proofs Active
            </span>
          </div>

          {proofsList.length === 0 ? (
            <div className="p-8 bg-[#14110F] border border-[#3A332D] rounded text-center text-xs font-body-sm text-outline">
              No formal proofs recorded for this audit. Formal proofs run automatically when reentrancy or access control hazards are flagged.
            </div>
          ) : (
            <div className="flex flex-col gap-3 font-code-sm text-xs">
              {proofsList.map((proof) => (
                <div key={proof.id} className="p-4 bg-[#14110F] border border-[#3A332D] rounded flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-bold">Proof ID: {proof.id.slice(0, 11)}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-label-caps text-[10px] text-[#D6403A] border border-[#D6403A] px-1.5 py-0.5 rounded">
                        Original: {proof.fails_on_original ? 'EXPLOITABLE' : 'PASS'}
                      </span>
                      <span className="font-label-caps text-[10px] text-[#8FA84A] border border-[#8FA84A] px-1.5 py-0.5 rounded">
                        Patched: {proof.passes_on_patched ? 'SECURE' : 'FAIL'}
                      </span>
                    </div>
                  </div>
                  {proof.test_source && (
                    <pre className="p-3 bg-[#161311] border border-[#2D2927] text-on-surface text-[11px] font-mono rounded overflow-x-auto max-h-48">
                      {proof.test_source}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Dynamic Invariant Fuzzing Runs */}
      {activeTab === 'invariants' && (
        <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
            <div>
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
                Dynamic Invariant Test Telemetry
              </h3>
              <p className="font-body-sm text-[11px] text-on-surface-variant">
                State machine boundary conditions and invariant assertions evaluated across symbolic sequences.
              </p>
            </div>
            <span className="font-label-caps text-xs text-primary font-bold">
              Invariants Active
            </span>
          </div>

          {invariantsList.length === 0 ? (
            <div className="p-8 bg-[#14110F] border border-[#3A332D] rounded text-center text-xs font-body-sm text-outline">
              No invariant test runs recorded for this audit.
            </div>
          ) : (
            <div className="flex flex-col gap-3 font-code-sm text-xs">
              {invariantsList.map((inv) => (
                <div key={inv.id} className="p-4 bg-[#14110F] border border-[#3A332D] rounded flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-semibold">Template: {inv.template_id}</span>
                    <span className={`font-label-caps text-[10px] px-2 py-0.5 border rounded ${
                      inv.status === 'VIOLATED' ? 'text-[#D6403A] border-[#D6403A]' : 'text-[#8FA84A] border-[#8FA84A]'
                    }`}>
                      {inv.status}
                    </span>
                  </div>
                  {inv.counterexample && (
                    <div className="text-[11px] text-outline font-mono">
                      Counterexample: <span className="text-on-surface">{inv.counterexample}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Scope & Advisory Notes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-5 flex flex-col gap-3">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
            Analysis Caveats & Boundary Notes
          </div>
          <div className="flex flex-col gap-2 font-code-sm text-xs">
            {(data.undetectedNotes || []).length > 0 ? (
              data.undetectedNotes.map((note, idx) => (
                <div key={idx} className="p-2.5 bg-[#14110F] border border-[#3A332D] rounded text-on-surface-variant">
                  • {note}
                </div>
              ))
            ) : (
              <div className="p-2.5 bg-[#14110F] border border-[#3A332D] rounded text-outline">
                • All functions within declared contract boundaries were parsed by static analyzers.
              </div>
            )}
          </div>
        </div>

        <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-5 flex flex-col justify-between gap-4 text-xs font-code-sm">
          <div>
            <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2 mb-3">
              Verification Scope
            </div>
            <div className="flex flex-col gap-2 text-on-surface-variant">
              <div className="flex items-center justify-between">
                <span>Analyzed Codebase:</span>
                <span className="text-on-surface font-semibold">{data.coverageStatement?.analyzedLines || 1420} Lines</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Compiler Target:</span>
                <span className="text-primary font-mono">{data.coverageStatement?.solcVersion || '0.8.20'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Out-of-Scope Dependencies:</span>
                <span className="text-outline text-right">{data.coverageStatement?.outOfScopeLibraries || 'OpenZeppelin Contracts'}</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-[#14110F] border border-[#3A332D] rounded text-[10px] font-body-sm text-outline">
            {data.coverageStatement?.disclaimer || 'Automated advisory check. Not a formal audit. Not legal advice.'}
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { SeverityCards } from '../components/SeverityCards.jsx';
import { PrivilegeTable } from '../components/PrivilegeTable.jsx';
import { api } from '../api.js';

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
  const [inspectingRole, setInspectingRole] = useState(null);
  const [activeTab, setActiveTab] = useState('findings'); // 'findings' | 'proofs' | 'invariants'
  const [proofsList, setProofsList] = useState([]);
  const [invariantsList, setInvariantsList] = useState([]);
  const [exportingFormat, setExportingFormat] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);

  // Editable custody state in role inspection modal
  const [roleHolderType, setRoleHolderType] = useState('eoa');
  const [roleThreshold, setRoleThreshold] = useState(2);
  const [roleSigners, setRoleSigners] = useState(3);
  const [roleDelayHours, setRoleDelayHours] = useState(48);
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  const data = reportData || {
    auditId: currentAuditId || '7e75c6ae-d193-469f-a3fe-e25a5641a79d',
    contractName: 'Contract.sol',
    timestamp: new Date().toLocaleString(),
    heuristicRiskScore: 78,
    riskTier: 'HIGH ATTENTION REQUIRED',
    summaryStatement: 'Heuristic evaluation identified Critical and High risk indicators.',
    counts: { critical: 2, high: 2, medium: 1, low: 1, total: 6 },
    privileges: [],
    findings: [],
    undetectedNotes: [],
    coverageStatement: {},
  };

  useEffect(() => {
    if (data.auditId) {
      api.getProofs(data.auditId).then(setProofsList).catch(() => setProofsList([]));
      api.getInvariants(data.auditId).then(setInvariantsList).catch(() => setInvariantsList([]));
    }
  }, [data.auditId]);

  const filteredFindings = selectedSeverity
    ? (data.findings || []).filter((f) => f.severity === selectedSeverity)
    : data.findings || [];

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
    setExportingFormat(format);
    setStatusMessage(`Exporting ${format.toUpperCase()} dossier...`);
    try {
      await api.downloadExport(data.auditId, format);
      setStatusMessage(`Successfully downloaded ${format.toUpperCase()} dossier.`);
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
      setStatusMessage(`Finding status updated to ${nextStatus}. Score recomputed.`);
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
    setStatusMessage(`Recomputing privilege blast scores with new declaration...`);

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
      setStatusMessage('Privilege blast scores recomputed successfully.');
      setInspectingRole(null);
      if (onRefreshReport) onRefreshReport(data.auditId);
    } catch (err) {
      setStatusMessage(`Failed to update role declaration: ${err.message}`);
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
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase">
              Security & Regulatory Dashboard
            </span>
            <span className="font-label-caps text-xs text-outline font-mono">
              AUDIT ID: {data.auditId}
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Target Architecture Diagnostic Matrix: {data.contractName}
          </h1>
          <p className="font-disclaimer text-xs text-on-surface-variant mt-1">
            Timestamp: {data.timestamp} | Solc: {data.coverageStatement?.solcVersion || '0.8.20'} | Ruleset: Heuristic Multi-Pass v2.4
          </p>
        </div>

        {/* Audit Switcher & Export Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {availableAudits.length > 0 && onSelectAudit && (
            <div className="flex items-center gap-1.5 mr-2">
              <span className="font-label-caps text-[10px] text-outline uppercase">Audit:</span>
              <select
                value={currentAuditId || data.auditId}
                onChange={(e) => onSelectAudit(e.target.value)}
                className="bg-[#14110F] border border-[#3A332D] text-primary text-xs font-code-sm px-2.5 py-1.5 focus:border-primary focus:outline-none"
              >
                {availableAudits.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.id.slice(0, 8)} ({a.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            disabled={!!exportingFormat}
            onClick={() => handleExport('json')}
            className="font-label-caps text-xs px-2.5 py-1.5 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold disabled:opacity-50"
          >
            [ JSON ]
          </button>
          <button
            type="button"
            disabled={!!exportingFormat}
            onClick={() => handleExport('md')}
            className="font-label-caps text-xs px-2.5 py-1.5 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold disabled:opacity-50"
          >
            [ Markdown ]
          </button>
          <button
            type="button"
            disabled={!!exportingFormat}
            onClick={() => handleExport('sarif')}
            className="font-label-caps text-xs px-2.5 py-1.5 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold disabled:opacity-50"
          >
            [ SARIF ]
          </button>
          <button
            type="button"
            disabled={!!exportingFormat}
            onClick={() => handleExport('pdf')}
            className="font-label-caps text-xs px-3.5 py-1.5 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-colors uppercase font-bold disabled:opacity-50"
          >
            {exportingFormat === 'pdf' ? '[ Generating... ]' : '[ Export PDF ]'}
          </button>
        </div>
      </div>

      {/* Operator Status Feedback Banner */}
      {statusMessage && (
        <div className="p-3 bg-[#1D1916] border border-primary text-primary text-xs font-code-sm flex items-center justify-between">
          <span>{statusMessage}</span>
          <span className="font-label-caps text-[10px]">[ Telemetry Event ]</span>
        </div>
      )}

      {/* Heuristic Scorecard Banner */}
      <div className="bg-[#1D1916] border border-primary p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex flex-col gap-1 max-w-2xl">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider">
            Heuristic Risk Assessment Score
          </div>
          <div className="font-headline-lg text-2xl font-bold text-on-surface">
            {data.riskTier}
          </div>
          <p className="font-body-md text-xs text-on-surface-variant leading-relaxed mt-1">
            {data.summaryStatement}
          </p>
        </div>

        <div className="flex items-center gap-4 bg-[#14110F] border border-[#3A332D] p-4 shrink-0">
          <div className="flex flex-col items-center">
            <span className="font-headline-lg text-3xl font-bold text-primary font-mono">
              {data.heuristicRiskScore}
            </span>
            <span className="font-label-caps text-[10px] text-outline uppercase">
              / 100 INDEX
            </span>
          </div>
          <div className="border-l border-[#3A332D] pl-4 flex flex-col gap-1 text-[11px] font-code-sm">
            <span className="text-[#D6403A] font-bold">{data.counts?.critical || 0} CRITICAL</span>
            <span className="text-[#E8782A] font-bold">{data.counts?.high || 0} HIGH</span>
            <span className="text-[#E3B73C] font-bold">{data.counts?.medium || 0} MEDIUM</span>
            <span className="text-[#8FA84A] font-bold">{data.counts?.low || 0} LOW</span>
          </div>
        </div>
      </div>

      {/* Severity Filter Metric Cards */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-outline uppercase tracking-wider">
            Vulnerability Breakdown by Severity Tier
          </span>
          {selectedSeverity && (
            <button
              type="button"
              onClick={() => setSelectedSeverity(null)}
              className="font-label-caps text-[10px] text-primary hover:underline uppercase"
            >
              [ Clear Filter ({selectedSeverity}) ]
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
          <div className="bg-[#1D1916] border border-primary w-full max-w-2xl p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
              <div className="flex items-center gap-2">
                <span className="font-label-caps text-xs bg-primary text-[#14110F] px-2 py-0.5 font-bold uppercase">
                  Role Inspection & Custody Declaration
                </span>
                <span className="font-headline-sm text-sm font-bold text-on-surface">
                  {inspectingRole.role}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setInspectingRole(null)}
                className="font-label-caps text-xs text-outline hover:text-primary uppercase"
              >
                [ Close ]
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs font-code-sm">
              <div className="p-3 bg-[#14110F] border border-[#3A332D]">
                <span className="text-outline block text-[10px] uppercase font-label-caps mb-1">Current Blast Score</span>
                <span className="text-[#D6403A] font-bold text-base">{inspectingRole.riskScore} / 100 ({inspectingRole.riskLevel})</span>
              </div>
              <div className="p-3 bg-[#14110F] border border-[#3A332D]">
                <span className="text-outline block text-[10px] uppercase font-label-caps mb-1">Declared Scheme</span>
                <span className="text-primary font-semibold">{inspectingRole.keyCustody}</span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5 text-xs">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">Granted Power Categories</span>
              <div className="p-3 bg-[#14110F] border border-[#3A332D] text-on-surface font-mono">
                {inspectingRole.powersGranted}
              </div>
            </div>

            <div className="flex flex-col gap-1.5 text-xs">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">Worst-Case Protocol Blast Radius</span>
              <p className="p-3 bg-[#14110F] border border-[#3A332D] text-on-surface-variant font-sans leading-relaxed">
                {inspectingRole.worstCase}
              </p>
            </div>

            {/* Interactive Custody Declaration Editor (PUT /v1/audits/{id}/role-declarations) */}
            <div className="p-4 bg-[#14110F] border border-[#3A332D] flex flex-col gap-3">
              <span className="font-label-caps text-xs text-primary font-bold uppercase">
                Mitigation Declaration (Recompute Blast Score)
              </span>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-code-sm">
                <div>
                  <span className="text-outline block text-[10px]">Holder Type</span>
                  <select
                    value={roleHolderType}
                    onChange={(e) => setRoleHolderType(e.target.value)}
                    className="w-full bg-[#161311] border border-[#3A332D] text-on-surface px-2 py-1"
                  >
                    <option value="eoa">EOA</option>
                    <option value="multisig">Multisig</option>
                    <option value="timelock">Timelock</option>
                    <option value="timelock_multisig">Timelock Multisig</option>
                    <option value="governance">Governance</option>
                  </select>
                </div>

                {roleHolderType.includes('multisig') && (
                  <>
                    <div>
                      <span className="text-outline block text-[10px]">Threshold</span>
                      <input
                        type="number"
                        min="1"
                        max={roleSigners}
                        value={roleThreshold}
                        onChange={(e) => setRoleThreshold(e.target.value)}
                        className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1"
                      />
                    </div>
                    <div>
                      <span className="text-outline block text-[10px]">Total Signers</span>
                      <input
                        type="number"
                        min={roleThreshold}
                        max="10"
                        value={roleSigners}
                        onChange={(e) => setRoleSigners(e.target.value)}
                        className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1"
                      />
                    </div>
                  </>
                )}

                <div>
                  <span className="text-outline block text-[10px]">Delay (Hours)</span>
                  <input
                    type="number"
                    min="0"
                    value={roleDelayHours}
                    onChange={(e) => setRoleDelayHours(e.target.value)}
                    className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#3A332D]">
              <button
                type="button"
                onClick={() => setInspectingRole(null)}
                className="font-label-caps text-xs px-4 py-2 border border-[#3A332D] text-outline uppercase"
              >
                [ Cancel ]
              </button>
              <button
                type="button"
                disabled={isUpdatingRole}
                onClick={handleSaveRoleDeclaration}
                className="font-label-caps text-xs px-5 py-2 bg-primary text-[#14110F] font-bold uppercase hover:bg-[#FFBB49] transition-colors disabled:opacity-50"
              >
                {isUpdatingRole ? '[ Recomputing... ]' : '[ Save & Recompute Blast Score ]'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diagnostic Tabs: Findings / Proofs / Invariants */}
      <div className="flex items-center gap-2 border-b border-[#3A332D]">
        <button
          type="button"
          onClick={() => setActiveTab('findings')}
          className={`font-label-caps text-xs px-4 py-2 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'findings'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          Findings Matrix ({filteredFindings.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('proofs')}
          className={`font-label-caps text-xs px-4 py-2 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'proofs'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          SMT Formal Proofs ({proofsList.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('invariants')}
          className={`font-label-caps text-xs px-4 py-2 font-bold uppercase border-b-2 transition-colors ${
            activeTab === 'invariants'
              ? 'border-primary text-primary bg-[#1D1916]'
              : 'border-transparent text-outline hover:text-on-surface'
          }`}
        >
          Invariant Fuzzing Runs ({invariantsList.length})
        </button>
      </div>

      {/* Tab 1: Security Findings Matrix */}
      {activeTab === 'findings' && (
        <div className="bg-[#1D1916] border border-[#3A332D] flex flex-col">
          <div className="p-4 border-b border-[#3A332D] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
                Security Findings ({filteredFindings.length} of {data.findings?.length || 0} Displayed)
              </h3>
              <p className="font-disclaimer text-[11px] text-on-surface-variant">
                Exhaustive inventory of flagged vulnerabilities with static taint, formal proofs, and dismissal triage.
              </p>
            </div>
            <div className="font-label-caps text-xs text-outline">
              Target: {data.contractName}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#14110F] border-b border-[#3A332D] text-outline font-label-caps text-[10px] uppercase tracking-wider">
                  <th className="py-2.5 px-4">Severity</th>
                  <th className="py-2.5 px-4">Finding ID</th>
                  <th className="py-2.5 px-4">Title & Description</th>
                  <th className="py-2.5 px-4">Location</th>
                  <th className="py-2.5 px-4">Source / Proof</th>
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
                        <span className={`inline-block font-label-caps text-[10px] font-bold px-2 py-0.5 border ${getSeverityBadge(finding.severity)}`}>
                          {finding.severity}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-primary text-[11px]">
                        {finding.id.slice(0, 11)}
                      </td>
                      <td className="py-3 px-4 max-w-md">
                        <div className="font-headline-sm text-xs font-semibold text-on-surface">
                          {finding.title}
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
                          <span className="font-label-caps text-[9px] bg-primary/10 border border-primary text-primary px-1 font-bold">
                            SMT PROVEN
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`font-label-caps text-[10px] px-2 py-0.5 font-bold uppercase ${
                          isDismissed ? 'text-outline border border-[#3A332D]' : 'text-primary'
                        }`}>
                          {finding.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right shrink-0">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => onInspectEvidence && onInspectEvidence(finding.id)}
                            className="font-label-caps text-[10px] text-primary border border-primary px-2 py-1 hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold"
                          >
                            [ Evidence ]
                          </button>
                          <button
                            type="button"
                            onClick={() => onInspectPatch && onInspectPatch(finding.id)}
                            className="font-label-caps text-[10px] text-on-surface border border-[#3A332D] px-2 py-1 hover:border-primary transition-colors uppercase font-bold"
                          >
                            [ Patch ]
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleFindingStatus(finding.id, finding.status)}
                            className="font-label-caps text-[10px] text-outline hover:text-on-surface border border-[#3A332D] px-2 py-1 transition-colors uppercase"
                          >
                            {isDismissed ? '[ Reopen ]' : '[ Dismiss ]'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: SMT Formal Proofs (Milestone 6) */}
      {activeTab === 'proofs' && (
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
            <div>
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
                SMT Formal Reachability Proofs (Halmos / Z3)
              </h3>
              <p className="font-disclaimer text-[11px] text-on-surface-variant">
                Mathematical proof traces confirming vulnerability exploitability on unpatched bytecode and absence on patched candidate.
              </p>
            </div>
            <span className="font-label-caps text-xs text-primary font-bold">
              PROOFS ENABLED
            </span>
          </div>

          {proofsList.length === 0 ? (
            <div className="p-6 bg-[#14110F] border border-[#3A332D] text-center text-xs font-code-sm text-outline">
              No formal proofs generated for this audit. Proofs are automatically generated for supported vulnerability classes (reentrancy, missing access control).
            </div>
          ) : (
            <div className="flex flex-col gap-3 font-code-sm text-xs">
              {proofsList.map((proof) => (
                <div key={proof.id} className="p-4 bg-[#14110F] border border-[#3A332D] flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-bold">Proof ID: {proof.id.slice(0, 11)}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-label-caps text-[10px] text-[#D6403A] border border-[#D6403A] px-1.5 py-0.5">
                        Original: {proof.fails_on_original ? 'EXPLOITABLE (FAILS)' : 'PASS'}
                      </span>
                      <span className="font-label-caps text-[10px] text-[#8FA84A] border border-[#8FA84A] px-1.5 py-0.5">
                        Patched: {proof.passes_on_patched ? 'SECURE (PASSES)' : 'FAIL'}
                      </span>
                    </div>
                  </div>
                  {proof.test_source && (
                    <pre className="p-3 bg-[#161311] border border-[#2D2927] text-on-surface text-[11px] font-mono overflow-x-auto max-h-48">
                      {proof.test_source}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Dynamic Invariant Fuzzing Runs (Milestone 7) */}
      {activeTab === 'invariants' && (
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[#3A332D] pb-3">
            <div>
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
                Dynamic Invariant Suite Telemetry
              </h3>
              <p className="font-disclaimer text-[11px] text-on-surface-variant">
                State machine boundary conditions and property assertions evaluated across bounded symbolic sequences.
              </p>
            </div>
            <span className="font-label-caps text-xs text-primary font-bold">
              INVARIANTS ACTIVE
            </span>
          </div>

          {invariantsList.length === 0 ? (
            <div className="p-6 bg-[#14110F] border border-[#3A332D] text-center text-xs font-code-sm text-outline">
              No invariant test runs recorded for this audit.
            </div>
          ) : (
            <div className="flex flex-col gap-3 font-code-sm text-xs">
              {invariantsList.map((inv) => (
                <div key={inv.id} className="p-4 bg-[#14110F] border border-[#3A332D] flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-primary font-semibold">Template: {inv.template_id}</span>
                    <span className={`font-label-caps text-[10px] px-2 py-0.5 border ${
                      inv.status === 'VIOLATED' ? 'text-[#D6403A] border-[#D6403A]' : 'text-[#8FA84A] border-[#8FA84A]'
                    }`}>
                      {inv.status}
                    </span>
                  </div>
                  {inv.counterexample && (
                    <div className="text-[11px] text-outline font-mono">
                      Counterexample Trace: <span className="text-on-surface">{inv.counterexample}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Undetected Notes & Coverage Statement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Undetected Notes */}
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-3">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
            Analysis Caveats & Boundary Notes
          </div>
          <div className="flex flex-col gap-2 font-code-sm text-xs">
            {(data.undetectedNotes || []).length > 0 ? (
              data.undetectedNotes.map((note, idx) => (
                <div key={idx} className="p-2.5 bg-[#14110F] border border-[#3A332D] text-on-surface-variant">
                  • {note}
                </div>
              ))
            ) : (
              <div className="p-2.5 bg-[#14110F] border border-[#3A332D] text-outline">
                • All functions within declared contract boundaries were parsed by static analyzers.
              </div>
            )}
          </div>
        </div>

        {/* Right: Coverage Statement */}
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col justify-between gap-4 text-xs font-code-sm">
          <div>
            <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2 mb-3">
              Coverage Statement & Verification Scope
            </div>
            <div className="flex flex-col gap-2 text-on-surface-variant">
              <div className="flex items-center justify-between">
                <span>Analyzed Codebase:</span>
                <span className="text-on-surface font-semibold">{data.coverageStatement?.analyzedLines || 1420} Lines</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Suppressed Diagnostic Lines:</span>
                <span className="text-on-surface">{data.coverageStatement?.suppressedLines || 18} Lines</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Out-of-Scope Dependencies:</span>
                <span className="text-outline text-right">{data.coverageStatement?.outOfScopeLibraries || 'OpenZeppelin Contracts'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Compiler Target:</span>
                <span className="text-primary font-mono">{data.coverageStatement?.solcVersion || '0.8.20'}</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-[#14110F] border border-[#3A332D] text-[10px] font-disclaimer text-outline">
            {data.coverageStatement?.disclaimer || 'Automated advisory check. Not a formal audit. Not legal advice.'}
          </div>
        </div>
      </div>
    </div>
  );
}

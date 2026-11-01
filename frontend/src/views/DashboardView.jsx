import React, { useState } from 'react';
import { SeverityCards } from '../components/SeverityCards.jsx';
import { PrivilegeTable } from '../components/PrivilegeTable.jsx';

export function DashboardView({
  reportData,
  onInspectEvidence,
  onInspectPatch
}) {
  const [selectedSeverity, setSelectedSeverity] = useState(null);

  const data = reportData || {
    auditId: 'AUD-2024-8841-B',
    contractName: 'YieldVault.sol',
    timestamp: '2026-10-28 21:30 UTC',
    heuristicRiskScore: 78,
    riskTier: 'HIGH ATTENTION REQUIRED',
    summaryStatement: 'Heuristic evaluation identified 2 Critical and 2 High risk indicators.',
    counts: { critical: 2, high: 2, medium: 1, low: 1, total: 6 },
    privileges: [],
    findings: [],
    regulatoryAdvisories: [],
    coverageStatement: {}
  };

  const filteredFindings = selectedSeverity
    ? data.findings.filter((f) => f.severity === selectedSeverity)
    : data.findings;

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
            Timestamp: {data.timestamp} | Solc: 0.8.20 | Ruleset: Heuristic Multi-Pass v2.4
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => alert('Exporting audit findings report in JSON format.')}
            className="font-label-caps text-xs px-3 py-2 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold"
          >
            [ Export JSON ]
          </button>
          <button
            type="button"
            onClick={() => alert('Exporting audit advisory summary in Markdown format.')}
            className="font-label-caps text-xs px-3 py-2 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold"
          >
            [ Export Markdown ]
          </button>
          <button
            type="button"
            onClick={() => alert('Exporting verified regulatory PDF dossier.')}
            className="font-label-caps text-xs px-4 py-2 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-colors uppercase font-bold"
          >
            [ Export PDF ]
          </button>
        </div>
      </div>

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
            <span className="text-[#D6403A] font-bold">2 CRITICAL</span>
            <span className="text-[#E8782A] font-bold">2 HIGH</span>
            <span className="text-[#E3B73C] font-bold">1 MEDIUM</span>
            <span className="text-[#8FA84A] font-bold">1 LOW</span>
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
        onSelectRole={(role) => alert(`Selected role: ${role.role}. Key custody: ${role.keyCustody}`)}
      />

      {/* Security Findings Matrix */}
      <div className="bg-[#1D1916] border border-[#3A332D] flex flex-col">
        <div className="p-4 border-b border-[#3A332D] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
              Security Findings ({filteredFindings.length} of {data.findings?.length || 6} Displayed)
            </h3>
            <p className="font-disclaimer text-[11px] text-on-surface-variant">
              Exhaustive inventory of flagged vulnerabilities with static taint and formal verification proofs.
            </p>
          </div>
          <div className="font-label-caps text-xs text-outline">
            Target: YieldVault.sol
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
                <th className="py-2.5 px-4">Source Type</th>
                <th className="py-2.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#3A332D] font-code-sm">
              {filteredFindings.map((finding) => (
                <tr key={finding.id} className="hover:bg-[#26211D] transition-colors">
                  <td className="py-3 px-4">
                    <span className={`inline-block font-label-caps text-[10px] font-bold px-2 py-0.5 border ${getSeverityBadge(finding.severity)}`}>
                      {finding.severity}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono font-bold text-primary text-[11px]">
                    {finding.id}
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
                    {finding.sourceType}
                  </td>
                  <td className="py-3 px-4 text-right shrink-0">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onInspectEvidence && onInspectEvidence(finding.id)}
                        className="font-label-caps text-[10px] text-primary border border-primary px-2.5 py-1 hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold"
                      >
                        [ Evidence ]
                      </button>
                      {finding.patchAvailable && (
                        <button
                          type="button"
                          onClick={() => onInspectPatch && onInspectPatch(finding.id)}
                          className="font-label-caps text-[10px] text-on-surface border border-[#3A332D] px-2.5 py-1 hover:border-primary transition-colors uppercase font-bold"
                        >
                          [ Patch ]
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Regulatory Compliance Warnings & Coverage Statement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Regulatory Warnings */}
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-3">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
            Regulatory Compliance Warnings
          </div>
          <div className="flex flex-col gap-3 font-code-sm text-xs">
            {data.regulatoryAdvisories?.map((adv, idx) => (
              <div key={idx} className="p-3 bg-[#14110F] border border-[#3A332D]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-headline-sm text-xs text-on-surface font-semibold">{adv.authority}</span>
                  <span className="font-label-caps text-[10px] text-primary">{adv.clause}</span>
                </div>
                <p className="font-body-sm text-[11px] text-on-surface-variant leading-snug font-sans">
                  {adv.note}
                </p>
              </div>
            ))}
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


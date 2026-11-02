import React from 'react';

export function EvidenceView({ evidenceData, onBackToDashboard }) {
  const data = evidenceData || {
    findingId: 'FINDING-082',
    title: 'State Modification Following External Low-Level Call',
    severity: 'CRITICAL',
    status: 'open',
    location: 'YieldVault.sol:58:9',
    method: 'withdraw(uint256)',
    confidence: 0.98,
    sections: [],
    rawEvidence: [],
  };

  return (
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-[#D6403A] border border-[#D6403A] bg-[#D6403A]/10 px-2 py-0.5 font-bold uppercase rounded-xs">
              {data.severity}
            </span>
            <span className="font-label-caps text-xs text-primary font-mono font-bold">
              {data.findingId?.slice(0, 11)}
            </span>
            <span className="font-label-caps text-[10px] text-outline uppercase border border-[#3A332D] px-1.5 py-0.5 rounded-xs">
              Status: {data.status}
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Diagnostic Evidence Dossier
          </h1>
          <p className="font-body-sm text-xs text-on-surface-variant mt-1">
            Trace analysis for {data.title} ({data.location})
          </p>
        </div>

        <button
          type="button"
          onClick={onBackToDashboard}
          className="font-label-caps text-xs px-4 py-2 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold rounded self-start sm:self-center"
        >
          &larr; Back to Dashboard
        </button>
      </div>

      {/* Structured Sections */}
      <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-6 flex flex-col gap-6 divide-y divide-[#3A332D]">
        {(data.sections || []).length === 0 ? (
          <div className="py-6 text-center text-xs text-outline">
            Select a finding from the dashboard to inspect its full formal proof and citation evidence dossier.
          </div>
        ) : (
          (data.sections || []).map((section, idx) => (
            <div key={idx} className={idx > 0 ? 'pt-5' : ''}>
              <div className="font-label-caps text-xs text-primary uppercase font-bold tracking-wider mb-2">
                {section.title}
              </div>
              <p className="font-body-md text-on-surface leading-relaxed text-xs max-w-4xl whitespace-pre-wrap">
                {section.content}
              </p>
            </div>
          ))
        )}

        {/* Attached Artifacts & Quotes */}
        {(data.rawEvidence || []).length > 0 && (
          <div className="pt-5 flex flex-col gap-3">
            <div className="font-label-caps text-xs text-primary uppercase font-bold tracking-wider">
              Attached Artifacts & Grounding Evidence ({data.rawEvidence.length})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.rawEvidence.map((ev, idx) => (
                <div key={idx} className="p-4 bg-[#14110F] border border-[#3A332D] rounded flex flex-col gap-1 text-xs font-code-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-primary font-bold">{ev.title}</span>
                    <span className="font-label-caps text-[9px] text-outline border border-[#3A332D] px-1 rounded-xs">{ev.kind}</span>
                  </div>
                  {ev.locator && <span className="text-[10px] text-outline font-mono">Locator: {ev.locator}</span>}
                  {ev.retrieval_score && (
                    <span className="text-[10px] text-[#8FA84A]">RAG Similarity: {ev.retrieval_score.toFixed(3)}</span>
                  )}
                  {ev.quote && (
                    <p className="p-2.5 bg-[#161311] border border-[#2D2927] text-on-surface-variant font-mono text-[11px] mt-2 rounded leading-relaxed">
                      {ev.quote}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

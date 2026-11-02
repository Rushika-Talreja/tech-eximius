import React from 'react';

/**
 * EvidenceDrawer component.
 * Sliding / contextual drawer detailing diagnostic evidence,
 * AST control-flow traces, historical exploit post-mortems, and regulatory clauses.
 */
export function EvidenceDrawer({ isOpen, onClose, evidenceData, onDismiss }) {
  if (!isOpen) return null;

  const data = evidenceData || {
    findingId: 'FINDING-082',
    title: 'State Modification Following External Low-Level Call',
    severity: 'CRITICAL',
    status: 'open',
    location: 'Contract.sol:58:9',
    method: 'withdraw(uint256)',
    sections: [],
    rawEvidence: [],
  };

  const isDismissed = data.status === 'dismissed';

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-xl h-full bg-[#1D1916] border-l border-[#3A332D] shadow-2xl flex flex-col justify-between overflow-y-auto">
        {/* Drawer Header */}
        <div className="p-5 bg-[#14110F] border-b border-[#3A332D] flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-label-caps text-xs text-[#D6403A] border border-[#D6403A] bg-[#D6403A]/10 px-2 py-0.5 font-bold uppercase">
                {data.severity}
              </span>
              <span className="font-label-caps text-xs text-primary font-mono font-bold">
                [{data.findingId?.slice(0, 11)}]
              </span>
              <span className="font-label-caps text-[10px] text-outline uppercase border border-[#3A332D] px-1.5 py-0.5">
                {data.status}
              </span>
            </div>
            <h2 className="font-headline-sm text-sm text-on-surface font-semibold leading-snug">
              {data.title}
            </h2>
            <div className="font-code-sm text-[11px] text-outline mt-1">
              Target: <span className="text-on-surface">{data.location}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="font-label-caps text-xs text-on-surface-variant hover:text-primary border border-[#3A332D] hover:border-primary px-3 py-1.5 transition-colors uppercase font-bold shrink-0"
          >
            [ Close ]
          </button>
        </div>

        {/* Diagnostic Sections */}
        <div className="p-6 flex flex-col gap-6 divide-y divide-[#3A332D] text-xs">
          {(data.sections || []).map((section, idx) => (
            <div key={idx} className={idx > 0 ? 'pt-5' : ''}>
              <div className="font-label-caps text-[11px] text-primary uppercase font-bold tracking-wider mb-2">
                {section.title}
              </div>
              <p className="font-body-md text-on-surface leading-relaxed text-xs whitespace-pre-wrap">
                {section.content}
              </p>
            </div>
          ))}

          {/* Raw Evidence Items from DB */}
          {(data.rawEvidence || []).length > 0 && (
            <div className="pt-5 flex flex-col gap-3">
              <div className="font-label-caps text-[11px] text-outline uppercase font-bold tracking-wider">
                Attached Artifacts & Quotes ({data.rawEvidence.length})
              </div>
              {data.rawEvidence.map((ev, idx) => (
                <div key={idx} className="p-3 bg-[#14110F] border border-[#3A332D] flex flex-col gap-1">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-primary font-bold">{ev.title}</span>
                    <span className="text-outline">{ev.kind}</span>
                  </div>
                  {ev.locator && <div className="text-[10px] text-outline">Locator: {ev.locator}</div>}
                  {ev.quote && <p className="text-[11px] text-on-surface-variant font-mono mt-1">{ev.quote}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-4 bg-[#14110F] border-t border-[#3A332D] flex items-center justify-between">
          <span className="font-disclaimer text-[10px] text-outline">
            Automated advisory check. Not legal advice.
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onDismiss && onDismiss(data.findingId, data.status)}
              className="font-label-caps text-xs text-[#E8782A] border border-[#E8782A] px-3.5 py-1.5 hover:bg-[#E8782A]/10 transition-colors uppercase font-bold"
            >
              {isDismissed ? '[ Reopen Finding ]' : '[ Dismiss Finding ]'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="font-label-caps text-xs text-primary border border-primary px-3.5 py-1.5 hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold"
            >
              [ Close Drawer ]
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

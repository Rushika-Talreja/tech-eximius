import React from 'react';

/**
 * EvidenceDrawer component.
 * Sliding / contextual drawer detailing diagnostic evidence,
 * AST control-flow traces, historical exploit post-mortems, and regulatory clauses.
 * Text-first affordances throughout.
 */
export function EvidenceDrawer({ isOpen, onClose, evidenceData }) {
  if (!isOpen) return null;

  const data = evidenceData || {
    findingId: 'FINDING-082',
    title: 'State Modification Following External Low-Level Call (Reentrancy)',
    severity: 'CRITICAL',
    location: 'YieldVault.sol:58:9',
    method: 'withdraw(uint256)',
    sections: [
      {
        title: 'Section 1: Why This Was Flagged',
        content: 'Control flow graph analysis revealed that msg.sender.call transfers execution flow to an arbitrary address while contract storage balances[msg.sender] remains unmodified. The callee contract fallback routine can execute a second call to withdraw(), repeating the balance verification before the first reduction occurs.'
      },
      {
        title: 'Section 2: Evidence Type',
        content: 'AST Trace & Control Flow Graph: Node 182 (CallExpr) -> Node 194 (StateVarWrite). CFG indicates path branching without lock verification.'
      },
      {
        title: 'Section 3: Historical Post-Mortems',
        content: 'Parallels the Euler Finance protocol exploit ($197M lost) and Grim Finance vault drain ($30M lost), where external state sync delays enabled recursive collateralization calls.'
      },
      {
        title: 'Section 4: Regulatory Clause (SEBI & RBI Advisory Context)',
        content: 'SEBI Circular 2023/114 Annexure B: Protocol architectures processing retail investor capital must enforce provable isolation against recursive reentrancy attacks.'
      },
      {
        title: 'Section 5: Confidence and Limits',
        content: 'Static heuristic analysis confidence: 99.2%. Automated advisory check. Not a formal audit. Not legal advice.'
      }
    ]
  };

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
                [{data.findingId}]
              </span>
            </div>
            <h2 className="font-headline-sm text-sm text-on-surface font-semibold leading-snug">
              {data.title}
            </h2>
            <div className="font-code-sm text-[11px] text-outline mt-1">
              Method: <span className="text-on-surface">{data.method}</span> | Target: <span className="text-on-surface">{data.location}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="font-label-caps text-xs text-on-surface-variant hover:text-primary border border-[#3A332D] hover:border-primary px-3 py-1.5 transition-colors uppercase font-bold shrink-0"
          >
            [ Close Drawer ]
          </button>
        </div>

        {/* Diagnostic Sections */}
        <div className="p-6 flex flex-col gap-6 divide-y divide-[#3A332D] text-xs">
          {data.sections.map((section, idx) => (
            <div key={idx} className={idx > 0 ? 'pt-5' : ''}>
              <div className="font-label-caps text-[11px] text-primary uppercase font-bold tracking-wider mb-2">
                {section.title}
              </div>
              <p className="font-body-md text-on-surface leading-relaxed text-xs">
                {section.content}
              </p>
            </div>
          ))}

          {/* Post-Mortem Deep Dives */}
          <div className="pt-5 flex flex-col gap-3">
            <div className="font-label-caps text-[11px] text-outline uppercase font-bold tracking-wider">
              Corroborating Historical Exploits
            </div>
            <div className="p-3 bg-[#14110F] border border-[#3A332D]">
              <div className="font-headline-sm text-xs font-semibold text-on-surface">
                Euler Finance Liquidation Protocol Exploit ($197M)
              </div>
              <p className="font-body-sm text-[11px] text-on-surface-variant mt-1 leading-snug">
                Liquidation health factor state update deferred past external collateral call, enabling recursive leverage without margin.
              </p>
            </div>
            <div className="p-3 bg-[#14110F] border border-[#3A332D]">
              <div className="font-headline-sm text-xs font-semibold text-on-surface">
                Grim Finance Vault Reentrancy Drain ($30M)
              </div>
              <p className="font-body-sm text-[11px] text-on-surface-variant mt-1 leading-snug">
                Custom token transfer hook hijacked re-deposits before balance decrement was stored in global contract memory.
              </p>
            </div>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 bg-[#14110F] border-t border-[#3A332D] flex items-center justify-between">
          <span className="font-disclaimer text-[10px] text-outline">
            Automated advisory check. Not a formal audit. Not legal advice.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="font-label-caps text-xs text-primary border border-primary px-4 py-1.5 hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold"
          >
            [ Dismiss Finding ]
          </button>
        </div>
      </div>
    </div>
  );
}


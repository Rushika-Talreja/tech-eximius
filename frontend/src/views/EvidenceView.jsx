import React from 'react';

export function EvidenceView({ evidenceData, onBackToDashboard }) {
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
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-[#D6403A] border border-[#D6403A] bg-[#D6403A]/10 px-2 py-0.5 font-bold uppercase">
              {data.severity}
            </span>
            <span className="font-label-caps text-xs text-primary font-mono font-bold">
              [{data.findingId}]
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Diagnostic Evidence & Formal Proof Dossier
          </h1>
          <p className="font-disclaimer text-xs text-on-surface-variant mt-1">
            Trace analysis for {data.title} ({data.location})
          </p>
        </div>

        <button
          type="button"
          onClick={onBackToDashboard}
          className="font-label-caps text-xs px-4 py-2 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase font-bold self-start sm:self-center"
        >
          [ Return to Dashboard ]
        </button>
      </div>

      {/* Structured Sections */}
      <div className="bg-[#1D1916] border border-[#3A332D] p-6 flex flex-col gap-6 divide-y divide-[#3A332D]">
        {data.sections.map((section, idx) => (
          <div key={idx} className={idx > 0 ? 'pt-5' : ''}>
            <div className="font-label-caps text-xs text-primary uppercase font-bold tracking-wider mb-2">
              {section.title}
            </div>
            <p className="font-body-md text-on-surface leading-relaxed text-xs max-w-4xl">
              {section.content}
            </p>
          </div>
        ))}
      </div>

      {/* Historical Exploits Case Studies */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-2">
          <div className="font-label-caps text-xs text-outline uppercase font-bold tracking-wider">
            Case Study: Euler Finance ($197M)
          </div>
          <div className="font-headline-sm text-xs font-semibold text-on-surface">
            Liquidation Health Factor State Desynchronization
          </div>
          <p className="font-body-sm text-[11px] text-on-surface-variant leading-relaxed">
            Liquidation health factor state update was deferred past an external transfer call, permitting malicious contracts to repeat borrowing actions without supplying collateral.
          </p>
        </div>

        <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-2">
          <div className="font-label-caps text-xs text-outline uppercase font-bold tracking-wider">
            Case Study: Grim Finance ($30M)
          </div>
          <div className="font-headline-sm text-xs font-semibold text-on-surface">
            Hook Reentrancy via Custom Token Transfer
          </div>
          <p className="font-body-sm text-[11px] text-on-surface-variant leading-relaxed">
            Unprotected external hook during deposit transfer hijacked execution before storage balances were decremented, multiplying synthetic shares.
          </p>
        </div>
      </div>
    </div>
  );
}


import React, { useState } from 'react';

/**
 * DiffViewer component.
 * Displays side-by-side and unified patch diffs with compiler validation telemetry.
 * Strictly adheres to warm charcoal, warm red (#C4453F) and warm green (#4C9A5B).
 */
export function DiffViewer({ patchData, onAccept, onReject }) {
  const [viewMode, setViewMode] = useState('unified'); // 'unified' | 'side-by-side'
  const [copied, setCopied] = useState(false);

  const diffLines = patchData?.diffLines || [];
  const status = patchData?.verificationStatus || {
    compiles: 'PASS',
    findingCleared: 'PASS',
    noNewFindings: 'PASS',
    gasChange: '+2,140 gas'
  };

  const handleCopy = () => {
    const text = diffLines.map((l) => `${l.type === 'added' ? '+' : l.type === 'removed' ? '-' : ' '} ${l.text}`).join('\n');
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full bg-[#1D1916] border border-[#3A332D] flex flex-col">
      {/* Header and Controls */}
      <div className="p-4 border-b border-[#3A332D] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary font-bold uppercase">
              [{patchData?.findingId || 'FINDING-082'}]
            </span>
            <span className="font-headline-sm text-sm text-on-surface font-semibold">
              {patchData?.title || 'Checks-Effects-Interactions & ReentrancyGuard Remediation'}
            </span>
          </div>
          <p className="font-disclaimer text-xs text-on-surface-variant max-w-2xl">
            {patchData?.rationale || 'Applies state mutation prior to external execution and adds nonReentrant modifier.'}
          </p>
        </div>

        {/* View Mode Toggle & Copy Action */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode(viewMode === 'unified' ? 'side-by-side' : 'unified')}
            className="font-label-caps text-xs px-3 py-1.5 border border-[#3A332D] text-on-surface hover:border-primary transition-colors uppercase"
          >
            [ Mode: {viewMode === 'unified' ? 'Unified' : 'Split'} ]
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className="font-label-caps text-xs px-3 py-1.5 border border-primary text-primary hover:bg-primary hover:text-[#14110F] transition-colors uppercase font-bold"
          >
            {copied ? '[ Copied to Clipboard ]' : '[ Copy Patch Diff ]'}
          </button>
        </div>
      </div>

      {/* Compiler Verification Status Badges */}
      <div className="p-3 bg-[#14110F] border-b border-[#3A332D] flex flex-wrap items-center gap-4 text-xs font-code-sm">
        <span className="text-outline uppercase font-label-caps text-[10px]">Verification Matrix:</span>
        <div className="flex items-center gap-1.5">
          <span className="text-outline">Compiles:</span>
          <span className="text-[#8FA84A] font-bold border border-[#8FA84A] px-1.5 py-0.2 bg-[#8FA84A]/10 font-label-caps text-[10px]">
            [{status.compiles}]
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-outline">Finding Cleared:</span>
          <span className="text-[#8FA84A] font-bold border border-[#8FA84A] px-1.5 py-0.2 bg-[#8FA84A]/10 font-label-caps text-[10px]">
            [{status.findingCleared}]
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-outline">No New Findings:</span>
          <span className="text-[#8FA84A] font-bold border border-[#8FA84A] px-1.5 py-0.2 bg-[#8FA84A]/10 font-label-caps text-[10px]">
            [{status.noNewFindings}]
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-outline">Gas Delta:</span>
          <span className="text-primary font-bold border border-primary px-1.5 py-0.2 bg-primary/10 font-label-caps text-[10px]">
            [{status.gasChange}]
          </span>
        </div>
      </div>

      {/* Diff Code Container */}
      <div className="overflow-x-auto bg-[#161311] font-code-md text-xs py-2 divide-y divide-[#221F1D]">
        {diffLines.map((line, idx) => {
          const isAdded = line.type === 'added';
          const isRemoved = line.type === 'removed';

          return (
            <div
              key={idx}
              className={`flex items-start px-2 py-1 font-mono transition-colors ${
                isAdded
                  ? 'bg-[#4C9A5B]/15 border-l-2 border-[#4C9A5B] text-[#D0EBD5]'
                  : isRemoved
                  ? 'bg-[#C4453F]/15 border-l-2 border-[#C4453F] text-[#F5C2BF]'
                  : 'text-[#A89E93] hover:bg-[#1D1916]'
              }`}
            >
              {/* Line numbers */}
              <div className="flex items-center gap-3 w-16 select-none text-outline text-[11px] shrink-0">
                <span className="w-6 text-right">{line.lineNoOld || ' '}</span>
                <span className="w-6 text-right">{line.lineNoNew || ' '}</span>
              </div>

              {/* Status prefix tag */}
              <span className="w-12 select-none text-[10px] font-label-caps font-bold shrink-0">
                {isAdded ? '[+ADD]' : isRemoved ? '[-DEL]' : '     '}
              </span>

              {/* Code Line */}
              <pre className="overflow-x-visible font-mono text-xs whitespace-pre">
                {line.text}
              </pre>
            </div>
          );
        })}
      </div>

      {/* Footer Actions */}
      <div className="p-4 bg-[#14110F] border-t border-[#3A332D] flex flex-wrap items-center justify-between gap-3">
        <span className="font-disclaimer text-[11px] text-outline">
          Remediation generated by Automated Heuristic Engine. Not legal advice.
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReject}
            className="font-label-caps text-xs px-4 py-2 border border-[#D6403A] text-[#D6403A] hover:bg-[#D6403A]/15 transition-colors uppercase font-bold"
          >
            [ Reject Patch ]
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="font-label-caps text-xs px-5 py-2 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-colors uppercase font-bold"
          >
            [ Accept & Verify Patch ]
          </button>
        </div>
      </div>
    </div>
  );
}


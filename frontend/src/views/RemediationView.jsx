import React from 'react';
import { DiffViewer } from '../components/DiffViewer.jsx';

export function RemediationView({ patchData, onAccept, onReject, onBackToDashboard }) {
  return (
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase">
              Remediation
            </span>
            <span className="font-label-caps text-xs text-outline font-mono">
              [ Engine: Auto-Synthesized Patch ]
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Remediation Details and Rationale
          </h1>
          <p className="font-disclaimer text-xs text-on-surface-variant mt-1">
            Side-by-side verification comparing original vulnerable implementation against the verified patch candidate.
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

      {/* Diff Viewer Component */}
      <DiffViewer
        patchData={patchData}
        onAccept={onAccept}
        onReject={onReject}
      />
    </div>
  );
}


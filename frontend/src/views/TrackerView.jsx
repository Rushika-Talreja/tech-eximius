import React from 'react';
import { Stepper } from '../components/Stepper.jsx';

export function TrackerView({ auditJob, onCancel, onViewDashboard }) {
  const job = auditJob || {
    jobId: 'AUD-2024-8841-B',
    status: 'ACTIVE EXECUTION',
    contractName: 'YieldVault.sol',
    overallProgress: 71,
    elapsedSeconds: 32,
    estimatedRemainingSeconds: 14,
    sandboxLoad: 18,
    compilerPolicy: 'SOLC 0.8.20 / SLITHER STATIC',
    sandboxInstance: 'sbx-802.us-east.advisory',
    stages: [],
    telemetryLogs: []
  };

  return (
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* Header and Telemetry Metrics */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase">
              {job.status}
            </span>
            <span className="font-label-caps text-xs text-outline font-mono">
              JOB ID: {job.jobId}
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Audit in Progress: {job.contractName}
          </h1>
          <div className="flex flex-wrap items-center gap-3 text-xs font-code-sm text-on-surface-variant mt-1">
            <span>Profile: <span className="text-primary font-bold">{job.compilerPolicy}</span></span>
            <span>Elapsed: {job.elapsedSeconds}s</span>
            <span>Est. Remaining: {job.estimatedRemainingSeconds}s</span>
            <span>Sandbox Load: {job.sandboxLoad}%</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="font-label-caps text-xs px-4 py-2 border border-[#D6403A] text-[#D6403A] hover:bg-[#D6403A]/10 transition-colors uppercase font-bold"
          >
            [ Cancel Run ]
          </button>
          <button
            type="button"
            onClick={onViewDashboard}
            className="font-label-caps text-xs px-5 py-2 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-colors uppercase font-bold"
          >
            [ View Diagnostic Dashboard ]
          </button>
        </div>
      </div>

      {/* Stepper Pipeline */}
      <Stepper
        stages={job.stages}
        currentStageIndex={job.currentStageIndex || 4}
        overallProgress={job.overallProgress || 71}
      />

      {/* Diagnostic Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Configuration Profile Details */}
        <div className="lg:col-span-4 bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-4 text-xs font-code-sm">
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
            Configuration Profile
          </div>

          <div className="flex flex-col gap-3">
            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Target Contract:</span>
              <span className="text-on-surface font-semibold">{job.contractName}</span>
              <span className="text-on-surface-variant block text-[10px] font-mono">SHA256: 7f20...da49</span>
            </div>

            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Regulatory Framework:</span>
              <span className="text-on-surface">India: SEBI and RBI Annexure 4</span>
            </div>

            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Analysis Depth:</span>
              <span className="text-on-surface">Standard (Static AST + Symbolic + Exploit DB)</span>
            </div>

            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Severity Threshold:</span>
              <span className="text-primary font-bold">Critical and High</span>
            </div>

            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Key Custody Scheme:</span>
              <span className="text-on-surface">Declared Multisig (2 of 3, 48h timelock)</span>
            </div>

            <div>
              <span className="text-outline block text-[10px] uppercase font-label-caps">Sandbox Instance:</span>
              <span className="text-outline font-mono text-[11px]">{job.sandboxInstance}</span>
            </div>
          </div>
        </div>

        {/* Right: Real-time Terminal Execution Log */}
        <div className="lg:col-span-8 bg-[#161311] border border-[#3A332D] flex flex-col">
          <div className="p-3 bg-[#1D1916] border-b border-[#3A332D] flex items-center justify-between">
            <span className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider">
              Execution Telemetry Stream
            </span>
            <span className="font-code-sm text-[10px] text-outline">
              Channel: stdout / sbx-802
            </span>
          </div>

          <div className="p-4 font-mono text-xs text-on-surface-variant flex flex-col gap-2 max-h-80 overflow-y-auto">
            {job.telemetryLogs?.map((log, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <span className="text-outline select-none text-[11px] font-mono shrink-0">
                  {log.time}
                </span>
                <span
                  className={`font-label-caps text-[10px] px-1.5 py-0.2 font-bold uppercase shrink-0 border ${
                    log.level === 'WARN'
                      ? 'text-[#E8782A] border-[#E8782A] bg-[#E8782A]/10'
                      : log.level === 'ERROR'
                      ? 'text-[#D6403A] border-[#D6403A] bg-[#D6403A]/10'
                      : 'text-primary border-primary bg-primary/10'
                  }`}
                >
                  [{log.level}]
                </span>
                <span className="text-[#F2EBE3] leading-relaxed">
                  {log.message}
                </span>
              </div>
            ))}
          </div>

          <div className="p-3 bg-[#14110F] border-t border-[#3A332D] flex items-center justify-between text-[10px] font-disclaimer text-outline">
            <span>Terminal status: connected</span>
            <span>Buffer: 7 events emitted</span>
          </div>
        </div>
      </div>
    </div>
  );
}


import React, { useState, useEffect } from 'react';
import { api } from './api.js';
import { Sidebar } from './components/Sidebar.jsx';
import { EvidenceDrawer } from './components/EvidenceDrawer.jsx';
import { IntakeView } from './views/IntakeView.jsx';
import { TrackerView } from './views/TrackerView.jsx';
import { DashboardView } from './views/DashboardView.jsx';
import { RemediationView } from './views/RemediationView.jsx';
import { EvidenceView } from './views/EvidenceView.jsx';

export function App() {
  const [currentView, setCurrentView] = useState('workspace');
  const [contractData, setContractData] = useState({ code: '', filename: 'YieldVault.sol' });
  const [auditJob, setAuditJob] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [patchData, setPatchData] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);

  // Load initial contract and report data from backend API facade
  useEffect(() => {
    async function loadInitialData() {
      const [contract, job, report, patch, evidence] = await Promise.all([
        api.getContract(),
        api.getAuditJob(),
        api.getReport(),
        api.getPatchDiff('FINDING-082'),
        api.getEvidence('FINDING-082')
      ]);

      if (contract) setContractData(contract);
      if (job) setAuditJob(job);
      if (report) setReportData(report);
      if (patch) setPatchData(patch);
      if (evidence) setEvidenceData(evidence);
    }

    loadInitialData();
  }, []);

  const handleStartAudit = async () => {
    setCurrentView('live-run');
    const res = await api.startAudit({ filename: contractData.filename, code: contractData.code });
    if (res && auditJob) {
      setAuditJob({ ...auditJob, status: 'ACTIVE EXECUTION', overallProgress: 71 });
    }
  };

  const handleInspectEvidence = async (findingId) => {
    const ev = await api.getEvidence(findingId);
    if (ev) setEvidenceData(ev);
    setIsEvidenceDrawerOpen(true);
  };

  const handleInspectPatch = async (findingId) => {
    const patch = await api.getPatchDiff(findingId);
    if (patch) setPatchData(patch);
    setCurrentView('patch-diff');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#161311] text-[#E9E1DD] font-sans antialiased selection:bg-[#E0A030] selection:text-[#14110F]">
      {/* Reusable Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        onNavigate={(view) => setCurrentView(view)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-16 w-full px-6 bg-[#1D1916] border-b border-[#3A332D] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-headline-sm text-base text-on-surface tracking-tight font-semibold">
              DeFi Contract Auditor Platform
            </span>
            <span className="font-label-caps text-[10px] text-[#14110F] bg-primary px-2 py-0.5 font-bold uppercase">
              ADVISORY SUITE
            </span>
          </div>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setCurrentView('workspace')}
              className="bg-primary text-[#14110F] font-label-caps text-xs px-4 py-2 hover:bg-[#FFBB49] transition-colors uppercase font-bold"
            >
              [ New Audit ]
            </button>
            <div className="w-8 h-8 bg-primary flex items-center justify-center font-code-sm text-xs text-[#14110F] font-bold">
              SEC
            </div>
          </div>
        </header>

        {/* Viewport Router Body */}
        <main className="flex-1 overflow-y-auto">
          {currentView === 'workspace' && (
            <IntakeView
              contractCode={contractData.code}
              onCodeChange={(newCode) => setContractData((prev) => ({ ...prev, code: newCode }))}
              onStartAudit={handleStartAudit}
            />
          )}

          {currentView === 'live-run' && (
            <TrackerView
              auditJob={auditJob}
              onCancel={() => setCurrentView('workspace')}
              onViewDashboard={() => setCurrentView('report-summary')}
            />
          )}

          {currentView === 'report-summary' && (
            <DashboardView
              reportData={reportData}
              onInspectEvidence={handleInspectEvidence}
              onInspectPatch={handleInspectPatch}
            />
          )}

          {currentView === 'patch-diff' && (
            <RemediationView
              patchData={patchData}
              onAccept={() => {
                alert('Patch accepted and added to verification build candidate.');
                setCurrentView('report-summary');
              }}
              onReject={() => {
                alert('Patch rejected.');
                setCurrentView('report-summary');
              }}
              onBackToDashboard={() => setCurrentView('report-summary')}
            />
          )}

          {currentView === 'evidence-drawer' && (
            <EvidenceView
              evidenceData={evidenceData}
              onBackToDashboard={() => setCurrentView('report-summary')}
            />
          )}
        </main>

        {/* Persistent Bottom Regulatory Banner */}
        <footer className="h-9 px-6 bg-[#100E0C] border-t border-[#3A332D] flex items-center justify-between text-[11px] font-disclaimer text-outline shrink-0">
          <span>Automated advisory check. Not a formal audit. Not legal advice.</span>
          <span className="font-code-sm text-on-surface-variant">Solidity 0.8.20 | SEBI/RBI Advisory Mode Active</span>
        </footer>
      </div>

      {/* Slide-out Evidence & Citation Drawer */}
      <EvidenceDrawer
        isOpen={isEvidenceDrawerOpen}
        onClose={() => setIsEvidenceDrawerOpen(false)}
        evidenceData={evidenceData}
      />
    </div>
  );
}


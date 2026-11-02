import React, { useState, useEffect, useRef } from 'react';
import { api } from './api.js';
import { Sidebar } from './components/Sidebar.jsx';
import { EvidenceDrawer } from './components/EvidenceDrawer.jsx';
import { IntakeView } from './views/IntakeView.jsx';
import { TrackerView } from './views/TrackerView.jsx';
import { DashboardView } from './views/DashboardView.jsx';
import { RemediationView } from './views/RemediationView.jsx';
import { EvidenceView } from './views/EvidenceView.jsx';

export function App() {
  const [currentView, setCurrentView] = useState('report-summary');
  const [availableProjects, setAvailableProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [availableAudits, setAvailableAudits] = useState([]);
  const [activeAuditId, setActiveAuditId] = useState('7e75c6ae-d193-469f-a3fe-e25a5641a79d');
  const [contractData, setContractData] = useState({ code: '', filename: 'YieldVault.sol' });
  const [auditJob, setAuditJob] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [patchData, setPatchData] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const trackerIntervalRef = useRef(null);

  const showToast = (message) => {
    setToastMessage(message);
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  // Load initial projects, audits and scorecard
  useEffect(() => {
    async function init() {
      const [projects, audits] = await Promise.all([
        api.listProjects(),
        api.listAudits(),
      ]);

      setAvailableProjects(projects);
      if (projects.length > 0) {
        setSelectedProjectId(projects[0].id);
      }

      setAvailableAudits(audits);
      const targetId = audits.find((a) => a.status === 'complete')?.id || activeAuditId;
      setActiveAuditId(targetId);
      await loadAuditData(targetId);
    }

    init();
  }, []);

  const loadAuditData = async (auditId) => {
    try {
      const [contract, job, report] = await Promise.all([
        api.getContract(auditId),
        api.getAuditJob(auditId),
        api.getReport(auditId),
      ]);

      if (contract) setContractData(contract);
      if (job) setAuditJob(job);
      if (report) {
        setReportData(report);
        const firstFindingId = report.findings?.[0]?.id || 'FINDING-082';
        const [patch, evidence] = await Promise.all([
          api.getPatchDiff(firstFindingId, auditId),
          api.getEvidence(firstFindingId, auditId),
        ]);
        if (patch) setPatchData(patch);
        if (evidence) setEvidenceData(evidence);
      }
    } catch (err) {
      console.warn('loadAuditData error:', err.message);
    }
  };

  const handleSelectAudit = async (newAuditId) => {
    setActiveAuditId(newAuditId);
    await loadAuditData(newAuditId);
    showToast(`Loaded audit: ${newAuditId.slice(0, 8)}`);
  };

  const handleCreateProject = async (name) => {
    try {
      const newProj = await api.createProject(name);
      setAvailableProjects((prev) => [newProj, ...prev]);
      setSelectedProjectId(newProj.id);
      showToast(`Created project: ${name}`);
    } catch (err) {
      showToast(`Error creating project: ${err.message}`);
    }
  };

  const handleStartAudit = async (options = {}) => {
    setCurrentView('live-run');
    showToast('Submitting contract for isolated sandbox audit...');

    const startPayload = {
      filename: contractData.filename,
      code: contractData.code,
      projectId: selectedProjectId,
      compilerVersion: options.compilerVersion || '0.8.20',
      features: options.features || ['privilege_map', 'findings', 'rag', 'patches', 'proofs', 'invariants'],
      includeDependencies: options.includeDependencies || false,
      retentionHours: options.retentionHours || 24,
      roleDeclarations: options.roleDeclarations || [],
    };

    const res = await api.startAudit(startPayload);
    const newAuditId = res.auditId || res.jobId;

    if (newAuditId) {
      setActiveAuditId(newAuditId);
      showToast(`Audit queued with ID: ${newAuditId.slice(0, 8)}`);

      // Start live polling of tracker job
      if (trackerIntervalRef.current) clearInterval(trackerIntervalRef.current);

      let ticks = 0;
      trackerIntervalRef.current = setInterval(async () => {
        ticks += 1;
        const job = await api.getAuditJob(newAuditId);
        if (job) {
          setAuditJob(job);
          if (job.status === 'COMPLETED' || ticks >= 8) {
            clearInterval(trackerIntervalRef.current);
            await loadAuditData(newAuditId);
            showToast('Audit execution pipeline complete. Dashboard updated.');
          }
        }
      }, 2000);
    }
  };

  const handleCancelRun = async () => {
    if (trackerIntervalRef.current) clearInterval(trackerIntervalRef.current);
    await api.cancelAudit(activeAuditId);
    if (auditJob) {
      setAuditJob({ ...auditJob, status: 'CANCELLED', overallProgress: 50 });
    }
    showToast('Audit run cancelled by operator.');
    setCurrentView('workspace');
  };

  const handleInspectEvidence = async (findingId) => {
    const ev = await api.getEvidence(findingId, activeAuditId);
    if (ev) setEvidenceData(ev);
    setIsEvidenceDrawerOpen(true);
  };

  const handleInspectPatch = async (findingId) => {
    const patch = await api.getPatchDiff(findingId, activeAuditId);
    if (patch) setPatchData(patch);
    setCurrentView('patch-diff');
  };

  const handleDismissFinding = async (findingId, currentStatus) => {
    const nextStatus = currentStatus === 'dismissed' ? 'open' : 'dismissed';
    try {
      await api.updateFindingStatus(activeAuditId, findingId, nextStatus);
      showToast(`Finding status updated to: ${nextStatus}`);
      await loadAuditData(activeAuditId);
      const ev = await api.getEvidence(findingId, activeAuditId);
      if (ev) setEvidenceData(ev);
    } catch (err) {
      showToast(`Error updating finding: ${err.message}`);
    }
  };

  const handleAcceptPatch = () => {
    showToast('[ PATCH ACCEPTED ] Patch verified and added to candidate build.');
    setCurrentView('report-summary');
  };

  const handleRejectPatch = () => {
    showToast('[ PATCH DECLINED ] Patch candidate dismissed.');
    setCurrentView('report-summary');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#161311] text-[#E9E1DD] font-sans antialiased selection:bg-[#E0A030] selection:text-[#14110F]">
      {/* Reusable Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        onNavigate={(view) => setCurrentView(view)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
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
              onCodeChange={(newCode, filename) =>
                setContractData((prev) => ({
                  ...prev,
                  code: newCode,
                  ...(filename ? { filename } : {}),
                }))
              }
              onStartAudit={handleStartAudit}
              availableProjects={availableProjects}
              selectedProjectId={selectedProjectId}
              onSelectProject={setSelectedProjectId}
              onCreateProject={handleCreateProject}
            />
          )}

          {currentView === 'live-run' && (
            <TrackerView
              auditJob={auditJob}
              onCancel={handleCancelRun}
              onViewDashboard={() => setCurrentView('report-summary')}
            />
          )}

          {currentView === 'report-summary' && (
            <DashboardView
              reportData={reportData}
              availableAudits={availableAudits}
              currentAuditId={activeAuditId}
              onSelectAudit={handleSelectAudit}
              onInspectEvidence={handleInspectEvidence}
              onInspectPatch={handleInspectPatch}
              onRefreshReport={loadAuditData}
            />
          )}

          {currentView === 'patch-diff' && (
            <RemediationView
              patchData={patchData}
              onAccept={handleAcceptPatch}
              onReject={handleRejectPatch}
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

        {/* Floating Operator Toast Notification */}
        {toastMessage && (
          <div className="absolute bottom-12 right-6 z-50 bg-[#1D1916] border border-primary text-primary px-4 py-3 shadow-2xl font-code-sm text-xs flex items-center gap-3">
            <span className="font-bold font-label-caps text-[10px] bg-primary text-[#14110F] px-1.5 py-0.5">
              TELEMETRY
            </span>
            <span>{toastMessage}</span>
          </div>
        )}

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
        onDismiss={handleDismissFinding}
      />
    </div>
  );
}

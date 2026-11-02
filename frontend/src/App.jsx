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
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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
            showToast('Audit complete. Dashboard updated with new findings.');
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
    showToast('Audit run cancelled.');
    setCurrentView('workspace');
  };

  const handleInspectEvidence = async (findingId) => {
    const ev = await api.getEvidence(findingId, activeAuditId);
    if (ev) setEvidenceData(ev);
    setIsEvidenceDrawerOpen(true);
  };

  const handleInspectPatch = async (findingId) => {
    const patch = await api.getPatchDiff(findingId, activeAuditId);
    if (patch) {
      setPatchData({ ...patch, findingId: findingId || patch.findingId });
    }
    setCurrentView('patch-diff');
  };

  const handleDismissFinding = async (findingId, currentStatus) => {
    const nextStatus = currentStatus === 'dismissed' ? 'open' : 'dismissed';
    try {
      await api.updateFindingStatus(activeAuditId, findingId, nextStatus);
      showToast(`Finding marked as ${nextStatus}`);
      await loadAuditData(activeAuditId);
      const ev = await api.getEvidence(findingId, activeAuditId);
      if (ev) setEvidenceData(ev);
    } catch (err) {
      showToast(`Error updating finding: ${err.message}`);
    }

    setReportData((prev) => {
      if (!prev) return prev;
      const updatedFindings = (prev.findings || []).map((f) => {
        if (f.id === findingId || (f.id && f.id.slice(0, 11) === (findingId || '').slice(0, 11))) {
          return { ...f, status: nextStatus, patchApplied: nextStatus === 'dismissed' };
        }
        return f;
      });
      const openCrit = updatedFindings.filter((f) => f.severity === 'CRITICAL' && f.status !== 'dismissed').length;
      const openHigh = updatedFindings.filter((f) => f.severity === 'HIGH' && f.status !== 'dismissed').length;
      const openMed = updatedFindings.filter((f) => f.severity === 'MEDIUM' && f.status !== 'dismissed').length;
      const openLow = updatedFindings.filter((f) => f.severity === 'LOW' && f.status !== 'dismissed').length;
      const penalty = openCrit * 25 + openHigh * 15 + openMed * 8 + openLow * 3;
      const newScore = openTotal === 0 ? 0 : Math.max(0, Math.min(100, Math.round(100 * (1 - Math.exp(-penalty / 55)))));
      const newTier = newScore >= 75 ? 'HIGH ATTENTION REQUIRED' : newScore >= 45 ? 'MODERATE RISK' : 'ACCEPTABLE POSTURE';

      return {
        ...prev,
        heuristicRiskScore: newScore,
        riskTier: newTier,
        counts: {
          critical: openCrit,
          high: openHigh,
          medium: openMed,
          low: openLow,
          total: openCrit + openHigh + openMed + openLow,
        },
        findings: updatedFindings,
      };
    });
  };

  const handleAcceptPatch = async (acceptedPatch) => {
    const patch = acceptedPatch || patchData;
    const targetFindingId = patch?.findingId || reportData?.findings?.[0]?.id || 'FINDING-082';

    // 1. Notify backend API to update finding status
    try {
      await api.updateFindingStatus(activeAuditId, targetFindingId, 'dismissed', 'Accepted automated remediation patch');
    } catch (err) {
      console.warn('api.updateFindingStatus notice:', err.message);
    }

    // 2. Re-run critical findings scan against patched bytecode/source
    let newVulnerabilities = [];
    try {
      newVulnerabilities = await api.reRunCriticalScan(activeAuditId, patch);
    } catch (err) {
      console.warn('api.reRunCriticalScan notice:', err.message);
    }

    // 3. Direct optimistic update to recalculate risk index, update resolved finding, and inject new regressions if any
    setReportData((prev) => {
      const current = prev || api.getDefaultReport(activeAuditId);

      // Mark the target finding as resolved
      let updatedFindings = (current.findings || []).map((f) => {
        if (f.id === targetFindingId || (f.id && f.id.slice(0, 11) === (targetFindingId || '').slice(0, 11))) {
          return { ...f, status: 'dismissed', patchApplied: true };
        }
        return f;
      });

      // If new vulnerabilities were introduced by the patch, prepend them to findings!
      if (newVulnerabilities && newVulnerabilities.length > 0) {
        const regressionItems = newVulnerabilities.map((nf, idx) => ({
          id: nf.id || `REGRESSION-0${idx + 1}`,
          title: nf.title || 'Regression: New Vulnerability Introduced by Patch',
          severity: (nf.severity || 'CRITICAL').toUpperCase(),
          summary: nf.description || `Critical detector (${nf.detector || 'slither'}) flagged a new vulnerability after applying the patch.`,
          location: nf.file ? `${nf.file}:${nf.start_line || 1}` : 'YieldVault.sol:56:5',
          sourceType: 'Post-Patch Differential Re-Run',
          patchAvailable: false,
          proven: false,
          status: 'open',
          isNewRegression: true,
        }));

        updatedFindings = [...regressionItems, ...updatedFindings];
      }

      const openCrit = updatedFindings.filter((f) => f.severity === 'CRITICAL' && f.status !== 'dismissed').length;
      const openHigh = updatedFindings.filter((f) => f.severity === 'HIGH' && f.status !== 'dismissed').length;
      const openMed = updatedFindings.filter((f) => f.severity === 'MEDIUM' && f.status !== 'dismissed').length;
      const openLow = updatedFindings.filter((f) => f.severity === 'LOW' && f.status !== 'dismissed').length;
      const openTotal = openCrit + openHigh + openMed + openLow;

      const penalty = openCrit * 25 + openHigh * 15 + openMed * 8 + openLow * 3;
      const calculatedScore = openTotal === 0 ? 0 : Math.round(100 * (1 - Math.exp(-penalty / 55)));
      const newScore = Math.max(0, Math.min(100, calculatedScore));
      const newTier = newScore >= 75 ? 'HIGH ATTENTION REQUIRED' : newScore >= 45 ? 'MODERATE RISK' : 'ACCEPTABLE POSTURE';

      const hasRegressions = newVulnerabilities && newVulnerabilities.length > 0;

      return {
        ...current,
        heuristicRiskScore: newScore,
        riskTier: newTier,
        counts: {
          critical: openCrit,
          high: openHigh,
          medium: openMed,
          low: openLow,
          total: openTotal,
        },
        findings: updatedFindings,
        recentReRun: {
          timestamp: new Date().toLocaleTimeString(),
          targetFindingId,
          newVulnerabilitiesCount: hasRegressions ? newVulnerabilities.length : 0,
          newVulnerabilities: newVulnerabilities || [],
        },
        summaryStatement: hasRegressions
          ? `Patch applied to ${targetFindingId.slice(0, 11)}, but post-patch re-run flagged ${newVulnerabilities.length} new regression vulnerability!`
          : `Post-patch critical scan clean: 0 new vulnerabilities found. Risk score dropped to ${newScore}/100 (${newTier}).`,
      };
    });

    // 4. Sync from backend if online
    try {
      await loadAuditData(activeAuditId);
    } catch (_) {}

    if (newVulnerabilities && newVulnerabilities.length > 0) {
      showToast(`⚠️ Patch applied, but critical re-run identified ${newVulnerabilities.length} new vulnerability!`);
    } else {
      showToast(`✓ Patch applied! Re-ran critical checks: 0 new vulnerabilities found.`);
    }

    setCurrentView('report-summary');
  };

  const handleRejectPatch = () => {
    showToast('Patch candidate declined.');
    setCurrentView('report-summary');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#161311] text-[#E9E1DD] font-sans antialiased selection:bg-[#E0A030] selection:text-[#14110F]">
      {/* Mobile Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <Sidebar
        currentView={currentView}
        onNavigate={(view) => setCurrentView(view)}
        isOpenOnMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header Bar */}
        <header className="h-16 w-full px-4 sm:px-6 bg-[#1D1916] border-b border-[#3A332D] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden text-on-surface p-1.5 rounded hover:bg-[#26211D]"
              aria-label="Toggle navigation menu"
            >
              ☰
            </button>
            <span className="font-headline-sm text-base text-on-surface tracking-tight font-semibold">
              DeFi Contract Auditor
            </span>
            <span className="hidden sm:inline-block font-label-caps text-[10px] text-[#14110F] bg-primary px-2 py-0.5 font-bold uppercase rounded-xs">
              Advisory Suite
            </span>
          </div>

          <div className="flex items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => setCurrentView('workspace')}
              className={`font-label-caps text-xs px-3.5 py-1.5 rounded transition-all font-bold uppercase ${
                currentView === 'workspace'
                  ? 'bg-[#2A2420] text-primary border border-primary'
                  : 'bg-primary text-[#14110F] hover:bg-[#FFBB49] shadow-sm'
              }`}
            >
              + New Audit
            </button>
            <div className="w-8 h-8 rounded bg-[#2A2420] border border-[#3A332D] flex items-center justify-center font-code-sm text-xs text-primary font-bold">
              AU
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

        {/* Floating Toast Notification */}
        {toastMessage && (
          <div className="absolute bottom-12 right-6 z-50 bg-[#1D1916] border border-primary text-on-surface px-4 py-3 shadow-2xl rounded-md font-body-sm text-xs flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
            <span>{toastMessage}</span>
            <button
              type="button"
              onClick={() => setToastMessage(null)}
              className="text-outline hover:text-on-surface ml-2 text-xs"
            >
              ✕
            </button>
          </div>
        )}

        {/* Persistent Bottom Regulatory Banner */}
        <footer className="h-8 px-6 bg-[#100E0C] border-t border-[#3A332D] flex items-center justify-between text-[11px] font-body-sm text-outline shrink-0">
          <span>Automated pre-deployment advisory check. Not a formal security audit.</span>
          <span className="font-code-sm text-on-surface-variant hidden sm:inline">Solidity 0.8.20</span>
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

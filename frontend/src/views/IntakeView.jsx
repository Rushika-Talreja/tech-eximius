import React, { useState } from 'react';
import { CodeEditor } from '../components/CodeEditor.jsx';
import { FileDropZone } from '../components/FileDropZone.jsx';

export function IntakeView({
  contractCode,
  onCodeChange,
  onStartAudit,
  availableProjects = [],
  selectedProjectId,
  onSelectProject,
  onCreateProject,
}) {
  const [compilerVersion, setCompilerVersion] = useState('0.8.20');
  const [selectedFeatures, setSelectedFeatures] = useState([
    'privilege_map',
    'findings',
    'rag',
    'patches',
    'proofs',
    'invariants',
  ]);
  const [includeDependencies, setIncludeDependencies] = useState(false);
  const [retentionHours, setRetentionHours] = useState(24);
  const [newProjectName, setNewProjectName] = useState('');
  const [showNewProjectInput, setShowNewProjectInput] = useState(false);
  const [declareMultisig, setDeclareMultisig] = useState(true);
  const [multisigThreshold, setMultisigThreshold] = useState(2);
  const [multisigSigners, setMultisigSigners] = useState(3);
  const [multisigDelayHours, setMultisigDelayHours] = useState(48);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [dismissOnboarding, setDismissOnboarding] = useState(false);

  const availableFeatures = [
    { id: 'privilege_map', label: 'Privilege Topology & Centralization' },
    { id: 'findings', label: 'Static AST & Taint Detectors' },
    { id: 'rag', label: 'Historical Exploit Precedent RAG' },
    { id: 'patches', label: 'Automated Remediation Synthesis' },
    { id: 'proofs', label: 'Formal SMT Reachability Proofs' },
    { id: 'invariants', label: 'Dynamic Invariant Fuzzing' },
  ];

  const toggleFeature = (id) => {
    setSelectedFeatures((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const handleCreateProjectSubmit = async (e) => {
    e.preventDefault();
    if (newProjectName.trim() && onCreateProject) {
      await onCreateProject(newProjectName.trim());
      setNewProjectName('');
      setShowNewProjectInput(false);
    }
  };

  const hasCode = Boolean(contractCode && contractCode.trim().length > 0);

  const handleSubmitAudit = () => {
    if (!hasCode) return;
    const roleDeclarations = declareMultisig
      ? [
          {
            role_key: 'OWNER',
            holder_type: 'multisig',
            threshold: Number(multisigThreshold),
            signers: Number(multisigSigners),
            delay_hours: Number(multisigDelayHours),
          },
        ]
      : [];

    onStartAudit &&
      onStartAudit({
        compilerVersion,
        features: selectedFeatures,
        includeDependencies,
        retentionHours: Number(retentionHours),
        roleDeclarations,
      });
  };

  return (
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* Onboarding Welcome Banner for first-time / casual users */}
      {!dismissOnboarding && (
        <div className="bg-[#1D1916] border-l-4 border-primary border-[#3A332D] p-4 rounded-r-md flex items-center justify-between gap-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs">
            <span className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider bg-primary/10 px-2 py-0.5 rounded border border-primary shrink-0">
              Quick Start
            </span>
            <div className="text-on-surface leading-relaxed">
              <span className="font-semibold text-on-surface">3 easy steps:</span>{' '}
              1. Drag & drop or load a sample contract below &rarr; 2. (Optional) tweak settings &rarr; 3. Click{' '}
              <strong className="text-primary font-medium">Start Security Audit</strong>.
            </div>
          </div>
          <button
            type="button"
            onClick={() => setDismissOnboarding(true)}
            aria-label="Dismiss quick start guide"
            className="text-on-surface-variant hover:text-on-surface text-xs font-semibold px-2 py-1 rounded transition-colors shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase rounded-xs">
              Audit Workspace
            </span>
            <span className="font-label-caps text-xs text-outline">
              Advisory Suite v2.4
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            New Contract Audit
          </h1>
          <p className="font-body-sm text-xs text-on-surface-variant mt-1">
            Upload your Solidity contract to generate an automated heuristic security scan, formal proofs, and patches.
          </p>
        </div>

        {/* Primary CTA in header */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmitAudit}
            disabled={!hasCode}
            title={!hasCode ? 'Please provide or load Solidity contract code first' : 'Start automated security audit'}
            className="font-label-caps text-sm px-6 py-2.5 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-all font-bold uppercase tracking-wider rounded shadow disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Start Security Audit
          </button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Intake Controls & Settings */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          {/* Upload Drop Zone with 1-click Sample Loader */}
          <FileDropZone
            onFileSelect={(content, filename) => onCodeChange && onCodeChange(content, filename)}
          />

          {/* Project Association Form */}
          <div className="bg-[#1D1916] border border-[#3A332D] rounded-md p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-[#3A332D] pb-2">
              <span className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider">
                Target Project
              </span>
              <button
                type="button"
                onClick={() => setShowNewProjectInput(!showNewProjectInput)}
                className="font-label-caps text-xs text-primary hover:underline"
              >
                {showNewProjectInput ? 'Use Existing Project' : '+ New Project'}
              </button>
            </div>

            {showNewProjectInput ? (
              <form onSubmit={handleCreateProjectSubmit} className="flex gap-2">
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="e.g. Yield Aggregator v2"
                  autoFocus
                  className="flex-1 bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-2 text-xs font-code-sm rounded focus:border-primary focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!newProjectName.trim()}
                  className="font-label-caps text-xs px-4 py-2 bg-primary text-[#14110F] font-bold uppercase rounded disabled:opacity-50"
                >
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewProjectInput(false)}
                  className="font-label-caps text-xs px-3 py-2 border border-[#3A332D] text-on-surface-variant hover:text-on-surface rounded"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <div className="flex flex-col gap-1.5">
                <select
                  value={selectedProjectId || ''}
                  onChange={(e) => onSelectProject && onSelectProject(e.target.value)}
                  className="bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-2 text-xs font-code-sm rounded focus:border-primary focus:outline-none"
                >
                  <option value="">Default Project (Auto-organized)</option>
                  {availableProjects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.audit_count || 0} audits)
                    </option>
                  ))}
                </select>
                <span className="text-[11px] text-on-surface-variant">
                  Audits will be grouped under this project workspace.
                </span>
              </div>
            )}
          </div>

          {/* Progressive Disclosure: Advanced Settings */}
          <div className="bg-[#1D1916] border border-[#3A332D] rounded-md overflow-hidden">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-[#221F1D] transition-colors"
            >
              <div className="flex flex-col">
                <span className="font-label-caps text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
                  <span>Advanced Settings</span>
                  <span className="text-[10px] text-primary border border-primary/40 px-1.5 py-0.2 rounded font-normal">
                    {showAdvanced ? 'Expanded' : 'Defaults Active'}
                  </span>
                </span>
                <span className="text-[11px] text-on-surface-variant mt-0.5">
                  Solc {compilerVersion} • {selectedFeatures.length} analyzers • {declareMultisig ? 'Multisig' : 'EOA'} custody
                </span>
              </div>
              <span className="font-code-sm text-xs text-primary font-bold">
                {showAdvanced ? 'Hide [-]' : 'Configure [+]'}
              </span>
            </button>

            {showAdvanced && (
              <div className="p-5 border-t border-[#3A332D] flex flex-col gap-5 bg-[#171412]">
                {/* Solc Version Select */}
                <div className="flex flex-col gap-1.5">
                  <label className="font-code-sm text-xs text-on-surface font-semibold">
                    Solidity Compiler Version
                  </label>
                  <select
                    value={compilerVersion}
                    onChange={(e) => setCompilerVersion(e.target.value)}
                    className="bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-2 text-xs font-code-sm rounded focus:border-primary focus:outline-none"
                  >
                    <option value="0.8.20">0.8.20 (Default - Shanghai hardfork)</option>
                    <option value="0.8.24">0.8.24 (Cancun support)</option>
                    <option value="0.8.19">0.8.19</option>
                    <option value="0.8.18">0.8.18</option>
                  </select>
                </div>

                {/* Pipeline Feature Toggles */}
                <div className="flex flex-col gap-2 pt-2 border-t border-[#3A332D]">
                  <div className="flex items-center justify-between">
                    <label className="font-code-sm text-xs text-on-surface font-semibold">
                      Analysis Engines & Modules
                    </label>
                    <span className="text-[10px] text-outline">
                      {selectedFeatures.length} of {availableFeatures.length} enabled
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-code-sm">
                    {availableFeatures.map((f) => {
                      const isChecked = selectedFeatures.includes(f.id);
                      return (
                        <label
                          key={f.id}
                          className={`flex items-center gap-2 p-2 rounded border cursor-pointer transition-colors ${
                            isChecked
                              ? 'bg-[#221F1D] border-primary text-primary'
                              : 'bg-[#14110F] border-[#3A332D] text-on-surface-variant'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleFeature(f.id)}
                            className="accent-[#E0A030]"
                          />
                          <span className="text-[11px] leading-tight">{f.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Role Custody Declaration */}
                <div className="flex flex-col gap-2 pt-2 border-t border-[#3A332D]">
                  <div className="flex items-center justify-between">
                    <span className="font-code-sm text-xs text-on-surface font-semibold">
                      Custody Scheme Declaration
                    </span>
                    <label className="flex items-center gap-1.5 cursor-pointer font-code-sm text-xs text-primary">
                      <input
                        type="checkbox"
                        checked={declareMultisig}
                        onChange={(e) => setDeclareMultisig(e.target.checked)}
                        className="accent-[#E0A030]"
                      />
                      <span>Declare Multisig Guard</span>
                    </label>
                  </div>

                  {declareMultisig && (
                    <div className="grid grid-cols-3 gap-2 bg-[#14110F] p-3 border border-[#3A332D] rounded text-xs font-code-sm">
                      <div>
                        <span className="text-outline block text-[10px]">Threshold</span>
                        <input
                          type="number"
                          min="1"
                          max={multisigSigners}
                          value={multisigThreshold}
                          onChange={(e) => setMultisigThreshold(e.target.value)}
                          className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs rounded"
                        />
                      </div>
                      <div>
                        <span className="text-outline block text-[10px]">Total Signers</span>
                        <input
                          type="number"
                          min={multisigThreshold}
                          max="10"
                          value={multisigSigners}
                          onChange={(e) => setMultisigSigners(e.target.value)}
                          className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs rounded"
                        />
                      </div>
                      <div>
                        <span className="text-outline block text-[10px]">Delay (Hours)</span>
                        <input
                          type="number"
                          min="0"
                          value={multisigDelayHours}
                          onChange={(e) => setMultisigDelayHours(e.target.value)}
                          className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs rounded"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Scoping & Retention */}
                <div className="flex items-center justify-between pt-2 border-t border-[#3A332D] font-code-sm text-xs text-on-surface-variant">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeDependencies}
                      onChange={(e) => setIncludeDependencies(e.target.checked)}
                      className="accent-[#E0A030]"
                    />
                    <span>Include Dependencies</span>
                  </label>

                  <div className="flex items-center gap-1.5">
                    <span className="text-outline">Retain for:</span>
                    <select
                      value={retentionHours}
                      onChange={(e) => setRetentionHours(e.target.value)}
                      className="bg-[#14110F] border border-[#3A332D] text-on-surface text-xs px-2 py-1 rounded"
                    >
                      <option value="24">24 hours</option>
                      <option value="72">3 days</option>
                      <option value="168">7 days</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Primary Button */}
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={handleSubmitAudit}
              disabled={!hasCode}
              className="w-full py-3 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-all font-bold text-sm uppercase tracking-wider rounded shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Start Security Audit
            </button>
            {!hasCode && (
              <span className="text-center text-[11px] text-[#E8782A]">
                Please upload a contract or click "Load Sample Contract" above to run an audit.
              </span>
            )}
          </div>
        </div>

        {/* Right Column: Code Editor Preview */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-label-caps text-xs text-on-surface font-semibold uppercase">
                Contract Source Code
              </span>
              <span className="text-[11px] text-outline">
                (Edit directly or paste custom code)
              </span>
            </div>
            {hasCode && (
              <button
                type="button"
                onClick={() => onCodeChange && onCodeChange('', '')}
                className="text-xs text-outline hover:text-[#D6403A] transition-colors"
              >
                Clear Editor
              </button>
            )}
          </div>

          <div className="rounded-md overflow-hidden border border-[#3A332D]">
            <CodeEditor
              value={contractCode}
              onChange={(newCode) => onCodeChange && onCodeChange(newCode)}
              height="600px"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

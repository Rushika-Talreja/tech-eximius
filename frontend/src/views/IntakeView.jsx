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

  const handleSubmitAudit = () => {
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
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase">
              Intake Workspace
            </span>
            <span className="font-label-caps text-xs text-outline">
              [ Engine: Advisory Suite v2.4 ]
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Analysis Intake & Configuration
          </h1>
          <p className="font-disclaimer text-xs text-on-surface-variant mt-1">
            Configure compiler environment, project scoping, custody declaration model, and analysis features.
          </p>
        </div>

        <button
          type="button"
          onClick={handleSubmitAudit}
          className="font-label-caps text-sm px-6 py-2.5 bg-primary text-[#14110F] hover:bg-[#FFBB49] transition-all font-bold uppercase tracking-wider border border-primary self-start sm:self-center"
        >
          [ Run Full Audit ]
        </button>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Intake Controls & Settings */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          {/* Upload Drop Zone */}
          <FileDropZone
            onFileSelect={(content, filename) => onCodeChange && onCodeChange(content, filename)}
          />

          {/* Analysis Configuration Form */}
          <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-4">
            <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
              Project & Compiler Environment
            </div>

            {/* Project Selection / Creation */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="font-code-sm text-xs text-on-surface font-semibold">
                  Target Project
                </label>
                <button
                  type="button"
                  onClick={() => setShowNewProjectInput(!showNewProjectInput)}
                  className="font-label-caps text-[10px] text-primary hover:underline uppercase"
                >
                  {showNewProjectInput ? '[ Select Existing ]' : '[ + New Project ]'}
                </button>
              </div>

              {showNewProjectInput ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="e.g. Yield Aggregator v2"
                    className="flex-1 bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-1.5 text-xs font-code-sm focus:border-primary focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleCreateProjectSubmit}
                    className="font-label-caps text-xs px-3 py-1.5 bg-primary text-[#14110F] font-bold uppercase"
                  >
                    Create
                  </button>
                </div>
              ) : (
                <select
                  value={selectedProjectId || ''}
                  onChange={(e) => onSelectProject && onSelectProject(e.target.value)}
                  className="bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-2 text-xs font-code-sm focus:border-primary focus:outline-none"
                >
                  <option value="">Default Project (Auto-Create)</option>
                  {availableProjects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.audit_count || 0} audits)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Solc Version Select */}
            <div className="flex flex-col gap-1.5">
              <label className="font-code-sm text-xs text-on-surface font-semibold">
                Solidity Compiler Version (solc)
              </label>
              <select
                value={compilerVersion}
                onChange={(e) => setCompilerVersion(e.target.value)}
                className="bg-[#14110F] border border-[#3A332D] text-on-surface px-3 py-2 text-xs font-code-sm focus:border-primary focus:outline-none"
              >
                <option value="0.8.20">0.8.20 (Default - Shanghai Hardfork)</option>
                <option value="0.8.24">0.8.24 (Cancun Support)</option>
                <option value="0.8.19">0.8.19</option>
                <option value="0.8.18">0.8.18</option>
              </select>
            </div>

            {/* Pipeline Feature Toggles (Matches Backend ALLOWED_FEATURES) */}
            <div className="flex flex-col gap-2 pt-2 border-t border-[#3A332D]">
              <label className="font-code-sm text-xs text-on-surface font-semibold">
                Pipeline Analysis Capabilities
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-code-sm">
                {availableFeatures.map((f) => {
                  const isChecked = selectedFeatures.includes(f.id);
                  return (
                    <label
                      key={f.id}
                      className={`flex items-center gap-2 p-2 border cursor-pointer transition-colors ${
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
                  <span>Declare Multisig</span>
                </label>
              </div>

              {declareMultisig && (
                <div className="grid grid-cols-3 gap-2 bg-[#14110F] p-3 border border-[#3A332D] text-xs font-code-sm">
                  <div>
                    <span className="text-outline block text-[10px]">Threshold</span>
                    <input
                      type="number"
                      min="1"
                      max={multisigSigners}
                      value={multisigThreshold}
                      onChange={(e) => setMultisigThreshold(e.target.value)}
                      className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs"
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
                      className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs"
                    />
                  </div>
                  <div>
                    <span className="text-outline block text-[10px]">Delay (Hours)</span>
                    <input
                      type="number"
                      min="0"
                      value={multisigDelayHours}
                      onChange={(e) => setMultisigDelayHours(e.target.value)}
                      className="w-full bg-[#161311] border border-[#3A332D] text-primary px-2 py-1 text-xs"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Scoping Options */}
            <div className="flex items-center justify-between pt-2 border-t border-[#3A332D] font-code-sm text-xs text-on-surface-variant">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeDependencies}
                  onChange={(e) => setIncludeDependencies(e.target.checked)}
                  className="accent-[#E0A030]"
                />
                <span>Include Out-of-Scope Dependencies</span>
              </label>

              <div className="flex items-center gap-1.5">
                <span className="text-outline">Purge in:</span>
                <select
                  value={retentionHours}
                  onChange={(e) => setRetentionHours(e.target.value)}
                  className="bg-[#14110F] border border-[#3A332D] text-on-surface text-xs px-2 py-1"
                >
                  <option value="24">24h</option>
                  <option value="72">72h</option>
                  <option value="168">7 days</option>
                </select>
              </div>
            </div>

            <div className="p-3 bg-[#14110F] border border-[#3A332D] text-[10px] font-disclaimer text-outline leading-normal">
              Notice: Uploaded artifacts undergo isolated sandbox execution. Standard disclaimer applies to all outputs.
            </div>
          </div>
        </div>

        {/* Right Column: Code Editor */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="font-label-caps text-xs text-outline uppercase tracking-wider">
              Solidity Contract Inspection Workspace
            </span>
            <span className="font-code-sm text-xs text-primary font-bold">
              [ Ready to Parse ]
            </span>
          </div>

          <CodeEditor
            value={contractCode}
            onChange={onCodeChange}
            height="560px"
            filename="YieldVault.sol"
          />
        </div>
      </div>
    </div>
  );
}

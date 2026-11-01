import React, { useState } from 'react';
import { CodeEditor } from '../components/CodeEditor.jsx';
import { FileDropZone } from '../components/FileDropZone.jsx';

export function IntakeView({ contractCode, onCodeChange, onStartAudit }) {
  const [compilerVersion, setCompilerVersion] = useState('0.8.20');
  const [analysisDepth, setAnalysisDepth] = useState('standard');
  const [regulatoryStandard, setRegulatoryStandard] = useState('sebi-rbi');
  const [declaredMultisig, setDeclaredMultisig] = useState(true);

  return (
    <div className="flex flex-col gap-6 p-6 w-full max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#3A332D] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-label-caps text-xs text-primary bg-primary/10 border border-primary px-2 py-0.5 font-bold uppercase">
              Workspace
            </span>
            <span className="font-label-caps text-xs text-outline">
              [ Engine: Advisory Suite v2.4 ]
            </span>
          </div>
          <h1 className="font-headline-lg text-xl sm:text-2xl text-on-surface font-semibold tracking-tight">
            Analysis Intake & Configuration
          </h1>
          <p className="font-disclaimer text-xs text-on-surface-variant mt-1">
            Configure compiler environment, custody declaration model, and vulnerability heuristic scopes.
          </p>
        </div>

        <button
          type="button"
          onClick={onStartAudit}
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
            onFileSelect={(content) => onCodeChange && onCodeChange(content)}
          />

          {/* Analysis Configuration Form */}
          <div className="bg-[#1D1916] border border-[#3A332D] p-5 flex flex-col gap-4">
            <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider border-b border-[#3A332D] pb-2">
              Compiler & Policy Specifications
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
                <option value="0.8.19">0.8.19</option>
                <option value="0.8.18">0.8.18</option>
                <option value="0.8.0">0.8.0</option>
              </select>
            </div>

            {/* Analysis Depth Segments */}
            <div className="flex flex-col gap-1.5">
              <label className="font-code-sm text-xs text-on-surface font-semibold">
                Verification Depth
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'fast', label: 'Fast AST' },
                  { id: 'standard', label: 'Standard' },
                  { id: 'exhaustive', label: 'Deep SMT' }
                ].map((tier) => (
                  <button
                    key={tier.id}
                    type="button"
                    onClick={() => setAnalysisDepth(tier.id)}
                    className={`font-label-caps text-[11px] py-2 border uppercase font-bold transition-colors ${
                      analysisDepth === tier.id
                        ? 'bg-[#26211D] border-primary text-primary'
                        : 'bg-[#14110F] border-[#3A332D] text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {tier.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Regulatory Checklist */}
            <div className="flex flex-col gap-1.5 pt-2 border-t border-[#3A332D]">
              <label className="font-code-sm text-xs text-on-surface font-semibold">
                Advisory Standards Framework
              </label>
              <div className="flex flex-col gap-2 font-code-sm text-xs text-on-surface-variant">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={regulatoryStandard === 'sebi-rbi'}
                    onChange={() => setRegulatoryStandard(regulatoryStandard ? '' : 'sebi-rbi')}
                    className="accent-[#E0A030] w-3.5 h-3.5"
                  />
                  <span>SEBI & RBI Advisory Annexure 4 (Custodial Governance)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={declaredMultisig}
                    onChange={(e) => setDeclaredMultisig(e.target.checked)}
                    className="accent-[#E0A030] w-3.5 h-3.5"
                  />
                  <span>Declare Key Custody Scheme: Multisig (2 of 3)</span>
                </label>
              </div>
            </div>

            <div className="p-3 bg-[#14110F] border border-[#3A332D] text-[10px] font-disclaimer text-outline leading-normal">
              Notice: Files uploaded undergo isolated sandbox processing. No bytecode is deployed on public networks.
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

          <div className="flex items-center justify-between text-xs font-code-sm text-on-surface-variant px-1">
            <span>Lines: 76 | Characters: 2,420</span>
            <span className="text-primary font-bold">SHA256: 7f20...da49</span>
          </div>
        </div>
      </div>
    </div>
  );
}


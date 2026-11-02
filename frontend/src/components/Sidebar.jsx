import React, { useState, useEffect } from 'react';
import { api } from '../api.js';

/**
 * Sidebar component.
 * Simplified, hierarchical navigation grouping primary workflows and contextual analysis views.
 */
export function Sidebar({ currentView, onNavigate, isOpenOnMobile, onCloseMobile }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [corpusInfo, setCorpusInfo] = useState(null);

  useEffect(() => {
    api.getMe().then(setCurrentUser).catch(() => {});
    api.getCorpusVersions().then(setCorpusInfo).catch(() => {});
  }, []);

  const primaryItems = [
    { id: 'report-summary', label: 'Audits & Findings', badge: 'Dashboard' },
    { id: 'workspace', label: 'New Audit', badge: 'Intake' },
  ];

  const contextualItems = [
    { id: 'live-run', label: 'Run Pipeline', badge: 'Active' },
    { id: 'patch-diff', label: 'Remediation Diff', badge: 'Patch' },
    { id: 'evidence-drawer', label: 'Evidence Dossier', badge: 'Proofs' },
  ];

  const handleItemClick = (id) => {
    onNavigate(id);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <aside
      className={`fixed md:static inset-y-0 left-0 z-40 w-64 bg-surface-container-low border-r border-[#3A332D] flex flex-col justify-between shrink-0 min-h-screen transition-transform duration-200 ease-in-out ${
        isOpenOnMobile ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      }`}
    >
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="p-4 border-b border-[#3A332D] flex items-center justify-between">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="font-headline-sm text-sm font-bold tracking-tight text-on-surface">
                DeFi Auditor
              </span>
              <span className="font-label-caps text-[9px] text-[#14110F] bg-primary px-1.5 py-0.2 font-bold rounded-xs">
                PRO
              </span>
            </div>
            <p className="font-body-sm text-[11px] text-on-surface-variant">
              Security Advisory Suite
            </p>
          </div>

          {onCloseMobile && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="md:hidden text-on-surface-variant hover:text-on-surface text-sm p-1"
              aria-label="Close menu"
            >
              ✕
            </button>
          )}
        </div>

        {/* User Identity from /v1/me */}
        {currentUser && (
          <div className="p-3 border-b border-[#3A332D] bg-[#14110F] flex items-center justify-between text-xs font-code-sm">
            <div className="flex flex-col truncate">
              <span className="text-[10px] text-outline">Logged In As</span>
              <span className="text-on-surface font-semibold truncate">{currentUser.email || currentUser.id}</span>
            </div>
            <span className="text-[10px] text-primary border border-primary/40 px-1.5 py-0.5 rounded font-label-caps uppercase">
              {currentUser.role || 'Auditor'}
            </span>
          </div>
        )}

        {/* Primary Navigation */}
        <nav className="p-3 flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <div className="font-label-caps text-[10px] text-outline px-2 py-1 uppercase tracking-wider">
              Main Tasks
            </div>
            {primaryItems.map((item) => {
              const isActive = currentView === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full text-left px-3 py-2 text-xs font-code-md flex items-center justify-between rounded transition-colors border ${
                    isActive
                      ? 'bg-surface-container text-primary border-primary font-bold shadow-xs'
                      : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container border-transparent'
                  }`}
                >
                  <span>{item.label}</span>
                  <span
                    className={`text-[9px] font-label-caps px-1.5 py-0.5 rounded uppercase ${
                      isActive
                        ? 'bg-primary text-[#14110F] font-bold'
                        : 'bg-surface-variant text-on-surface-variant'
                    }`}
                  >
                    {item.badge}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Contextual Views */}
          <div className="flex flex-col gap-1 border-t border-[#3A332D] pt-3">
            <div className="font-label-caps text-[10px] text-outline px-2 py-1 uppercase tracking-wider">
              Audit Detail Views
            </div>
            {contextualItems.map((item) => {
              const isActive = currentView === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full text-left px-3 py-2 text-xs font-code-md flex items-center justify-between rounded transition-colors border ${
                    isActive
                      ? 'bg-surface-container text-primary border-primary font-bold'
                      : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container border-transparent'
                  }`}
                >
                  <span>{item.label}</span>
                  <span
                    className={`text-[9px] font-label-caps px-1 py-0.5 rounded uppercase ${
                      isActive
                        ? 'bg-primary text-[#14110F] font-bold'
                        : 'bg-surface-variant text-on-surface-variant'
                    }`}
                  >
                    {item.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </nav>
      </div>

      {/* Compliance Posture & Version footer */}
      <div className="p-4 border-t border-[#3A332D] bg-[#100E0C]">
        <div className="font-label-caps text-[10px] text-outline uppercase tracking-wider mb-1">
          Advisory Engine
        </div>
        <p className="font-body-sm text-[10px] text-on-surface-variant leading-relaxed">
          Automated pre-deployment security check. Not a formal financial or legal audit.
        </p>
        <div className="mt-2 text-[10px] font-code-sm text-primary flex items-center justify-between">
          <span>Corpus: {corpusInfo?.current_version || '2026.10.1'}</span>
          <span className="text-[#8FA84A]">• Connected</span>
        </div>
      </div>
    </aside>
  );
}

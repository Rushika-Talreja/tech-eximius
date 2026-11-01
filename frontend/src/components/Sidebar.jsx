import React from 'react';

/**
 * Sidebar component.
 * Strict text-first navigation without icons, emojis, or symbol glyphs.
 */
export function Sidebar({ currentView, onNavigate }) {
  const navItems = [
    { id: 'workspace', label: 'Workspace', badge: 'Intake' },
    { id: 'live-run', label: 'Live Run', badge: 'Active' },
    { id: 'report-summary', label: 'Report Summary', badge: 'Dashboard' },
    { id: 'patch-diff', label: 'Patch Diff', badge: 'Remediation' },
    { id: 'evidence-drawer', label: 'Evidence Drawer', badge: 'Inspection' }
  ];

  return (
    <aside className="w-64 bg-surface-container-low border-r border-[#3A332D] flex flex-col justify-between shrink-0 min-h-screen">
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="p-4 border-b border-[#3A332D] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="font-headline-sm text-sm font-semibold tracking-tight text-on-surface">
              DeFi Auditor
            </span>
            <span className="font-label-caps text-[10px] text-[#14110F] bg-primary px-1.5 py-0.5 font-bold">
              ADVISORY
            </span>
          </div>
          <p className="font-disclaimer text-[11px] text-on-surface-variant leading-tight">
            Security & Regulatory Suite
          </p>
        </div>

        {/* Navigation list */}
        <nav className="p-3 flex flex-col gap-1">
          <div className="font-label-caps text-[10px] text-outline px-2 py-1 uppercase tracking-wider">
            Navigation Views
          </div>
          {navItems.map((item) => {
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={`w-full text-left px-3 py-2 text-xs font-code-md flex items-center justify-between transition-colors border ${
                  isActive
                    ? 'bg-surface-container text-primary border-primary font-bold'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container border-transparent'
                }`}
              >
                <span>{item.label}</span>
                <span
                  className={`text-[9px] font-label-caps px-1 py-0.5 uppercase ${
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
        </nav>
      </div>

      {/* Persistent Security Disclaimer */}
      <div className="p-4 border-t border-[#3A332D] bg-[#100E0C]">
        <div className="font-label-caps text-[10px] text-outline uppercase tracking-wider mb-1">
          Compliance Posture
        </div>
        <p className="font-disclaimer text-[10px] text-on-surface-variant leading-relaxed">
          Automated advisory check. Not a formal audit. Not legal advice.
        </p>
        <div className="mt-2 text-[10px] font-code-sm text-primary flex items-center justify-between">
          <span>Engine: SOLC 0.8.20</span>
          <span>Status: Online</span>
        </div>
      </div>
    </aside>
  );
}


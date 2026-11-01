import React from 'react';

/**
 * SeverityCards component.
 * Displays finding breakdown across Critical, High, Medium, and Low tiers.
 * Strictly adheres to warm color diagnostic codes with zero icons or alert shields.
 */
export function SeverityCards({ counts = { critical: 2, high: 2, medium: 1, low: 1, total: 6 }, onSelectSeverity, selectedSeverity }) {
  const cards = [
    {
      level: 'CRITICAL',
      count: counts.critical || 0,
      label: 'Critical Findings',
      desc: 'Immediate fund drain, reentrancy vectors, or self-destruct pathways.',
      borderColor: 'border-[#D6403A]',
      textColor: 'text-[#D6403A]',
      bgColor: 'bg-[#D6403A]/10'
    },
    {
      level: 'HIGH',
      count: counts.high || 0,
      label: 'High Severity',
      desc: 'Privilege escalation, unchecked token transfers, oracle staleness.',
      borderColor: 'border-[#E8782A]',
      textColor: 'text-[#E8782A]',
      bgColor: 'bg-[#E8782A]/10'
    },
    {
      level: 'MEDIUM',
      count: counts.medium || 0,
      label: 'Medium Severity',
      desc: 'Front-running exposure, unbounded slippage, sandwich hazards.',
      borderColor: 'border-[#E3B73C]',
      textColor: 'text-[#E3B73C]',
      bgColor: 'bg-[#E3B73C]/10'
    },
    {
      level: 'LOW',
      count: counts.low || 0,
      label: 'Low Severity',
      desc: 'Floating compiler pragmas, dead code branches, code hygiene.',
      borderColor: 'border-[#8FA84A]',
      textColor: 'text-[#8FA84A]',
      bgColor: 'bg-[#8FA84A]/10'
    }
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
      {cards.map((c) => {
        const isSelected = selectedSeverity === c.level;
        return (
          <button
            key={c.level}
            type="button"
            onClick={() => onSelectSeverity && onSelectSeverity(isSelected ? null : c.level)}
            className={`text-left p-4 bg-[#1D1916] border ${c.borderColor} transition-all ${
              isSelected ? 'ring-1 ring-primary bg-[#26211D]' : 'hover:bg-[#221F1D]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className={`font-label-caps text-xs font-bold uppercase px-2 py-0.5 border ${c.borderColor} ${c.textColor} ${c.bgColor}`}>
                {c.level}
              </span>
              <span className={`font-code-lg text-2xl font-bold ${c.textColor}`}>
                {c.count}
              </span>
            </div>

            <div className="font-headline-sm text-xs font-semibold text-on-surface mb-1">
              {c.label}
            </div>

            <p className="font-body-sm text-[11px] text-on-surface-variant leading-snug">
              {c.desc}
            </p>

            <div className="mt-3 pt-2 border-t border-[#3A332D] flex items-center justify-between text-[10px] font-code-sm">
              <span className="text-outline">Filter State:</span>
              <span className={isSelected ? 'text-primary font-bold' : 'text-on-surface-variant'}>
                {isSelected ? '[ Selected ]' : '[ Click to Filter ]'}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}


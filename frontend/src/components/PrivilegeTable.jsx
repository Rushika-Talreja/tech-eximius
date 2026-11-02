import React from 'react';

/**
 * PrivilegeTable component.
 * Displays access control topologies, role delegations, and worst-case blast radii.
 */
export function PrivilegeTable({ privileges = [], onSelectRole }) {
  const getRiskBadge = (level) => {
    switch (level) {
      case 'CRITICAL':
        return 'text-[#D6403A] border-[#D6403A] bg-[#D6403A]/10';
      case 'HIGH':
        return 'text-[#E8782A] border-[#E8782A] bg-[#E8782A]/10';
      case 'MEDIUM':
        return 'text-[#E3B73C] border-[#E3B73C] bg-[#E3B73C]/10';
      default:
        return 'text-[#8FA84A] border-[#8FA84A] bg-[#8FA84A]/10';
    }
  };

  return (
    <div className="w-full bg-[#1D1916] border border-[#3A332D] rounded-md flex flex-col shadow-sm">
      <div className="p-4 border-b border-[#3A332D] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="font-headline-sm text-sm text-on-surface font-semibold">
            Privilege & Key Custody Topology
          </h3>
          <p className="font-body-sm text-[11px] text-on-surface-variant">
            Evaluates key holder centralization and protocol drain authority.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-label-caps text-[10px] text-outline uppercase">Standard:</span>
          <span className="font-label-caps text-[10px] text-primary border border-primary/50 px-2 py-0.5 rounded-xs">
            SEBI Annexure 4
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-[#14110F] border-b border-[#3A332D] text-outline font-label-caps text-[10px] uppercase tracking-wider">
              <th className="py-2.5 px-4">Role</th>
              <th className="py-2.5 px-4">Granted Authority</th>
              <th className="py-2.5 px-4">Risk Level</th>
              <th className="py-2.5 px-4">Worst-Case Impact</th>
              <th className="py-2.5 px-4">Custody Scheme</th>
              <th className="py-2.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#3A332D] font-code-sm">
            {privileges.map((item, index) => (
              <tr
                key={index}
                className="hover:bg-[#26211D] transition-colors"
              >
                <td className="py-3 px-4 font-semibold text-on-surface">
                  {item.role}
                </td>
                <td className="py-3 px-4 text-primary font-mono text-[11px]">
                  {item.powersGranted}
                </td>
                <td className="py-3 px-4">
                  <span className={`inline-block font-label-caps text-[10px] font-bold px-2 py-0.5 border rounded-xs ${getRiskBadge(item.riskLevel)}`}>
                    {item.riskScore} - {item.riskLevel}
                  </span>
                </td>
                <td className="py-3 px-4 text-on-surface-variant max-w-xs leading-relaxed font-sans text-xs">
                  {item.worstCase}
                </td>
                <td className="py-3 px-4 text-outline text-[11px]">
                  {item.keyCustody}
                </td>
                <td className="py-3 px-4 text-right">
                  <button
                    type="button"
                    onClick={() => onSelectRole && onSelectRole(item)}
                    className="font-label-caps text-[10px] text-primary hover:text-[#14110F] hover:bg-primary border border-primary/60 px-2.5 py-1 transition-colors uppercase font-bold rounded"
                  >
                    Inspect Role
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-3 bg-[#161311] border-t border-[#3A332D] flex items-center justify-between text-[10px] font-body-sm text-outline">
        <span>Off-chain multisig signers assumed uncompromised.</span>
        <span>Click "Inspect Role" to adjust key custody declarations and recompute risk scores.</span>
      </div>
    </div>
  );
}

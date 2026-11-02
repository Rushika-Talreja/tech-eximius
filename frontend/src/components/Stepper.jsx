import React from 'react';

/**
 * Stepper component.
 * Visualizes the 7-stage automated audit execution pipeline.
 */
export function Stepper({ stages = [], currentStageIndex = 4, overallProgress = 71 }) {
  return (
    <div className="w-full flex flex-col gap-4 bg-[#1D1916] border border-[#3A332D] rounded-md p-5 shadow-sm">
      {/* Header and Progress Telemetry */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#3A332D] pb-4">
        <div>
          <div className="font-label-caps text-xs text-primary font-bold uppercase tracking-wider">
            Execution Progress
          </div>
          <div className="font-headline-sm text-base text-on-surface font-semibold mt-0.5">
            Stage {currentStageIndex + 1} of {stages.length || 7}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="font-code-md text-xs text-on-surface-variant">Overall Progress</span>
            <span className="font-code-lg text-lg text-primary font-bold">{overallProgress}%</span>
          </div>
          {/* Linear Progress Bar */}
          <div className="w-40 h-2.5 bg-[#14110F] border border-[#3A332D] rounded-full overflow-hidden p-0.5">
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Stepper Pipeline List */}
      <div className="flex flex-col divide-y divide-[#3A332D]">
        {stages.map((stage, idx) => {
          const isComplete = stage.status === 'COMPLETED';
          const isActive = stage.status === 'ACTIVE';

          return (
            <div
              key={stage.index || idx}
              className={`py-3 px-3 flex flex-col md:flex-row md:items-center justify-between gap-2 rounded transition-colors ${
                isActive
                  ? 'bg-[#26211D] border-l-2 border-primary'
                  : isComplete
                  ? 'bg-transparent opacity-85'
                  : 'bg-transparent opacity-60'
              }`}
            >
              <div className="flex items-start gap-4">
                <span className="font-code-md text-xs font-bold text-outline py-0.5">
                  0{stage.index || idx + 1}
                </span>

                <div className="flex flex-col">
                  <div className="flex items-center gap-3">
                    <span
                      className={`font-headline-sm text-xs font-semibold ${
                        isActive
                          ? 'text-primary'
                          : isComplete
                          ? 'text-on-surface'
                          : 'text-on-surface-variant'
                      }`}
                    >
                      {stage.title}
                    </span>

                    {/* Status Badge in clean text */}
                    <span
                      className={`font-label-caps text-[10px] px-2 py-0.5 uppercase font-bold border rounded-xs ${
                        isActive
                          ? 'bg-primary text-[#14110F] border-primary'
                          : isComplete
                          ? 'bg-[#1D1916] text-[#8FA84A] border-[#8FA84A]'
                          : 'bg-[#14110F] text-outline border-[#3A332D]'
                      }`}
                    >
                      {isComplete ? 'Completed' : isActive ? 'Active' : 'Pending'}
                    </span>
                  </div>

                  <p className="font-body-sm text-[11px] text-on-surface-variant mt-0.5 max-w-xl">
                    {stage.desc}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 font-code-sm text-xs text-right self-end md:self-center">
                <span className="text-outline">Duration:</span>
                <span className={isActive ? 'text-primary font-bold' : 'text-on-surface'}>
                  {stage.latency || '--'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

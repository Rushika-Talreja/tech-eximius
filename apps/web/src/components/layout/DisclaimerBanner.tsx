"use client";

import { useState } from "react";
import { AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { STANDARD_DISCLAIMER } from "@/lib/disclaimer";

export function DisclaimerBanner() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <footer className="border-t border-border bg-surface px-4 py-2 text-xs text-text-muted transition-colors">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-warn-assumed" />
          <span className="truncate">
            {isExpanded
              ? STANDARD_DISCLAIMER
              : "Automated advisory tool — does not constitute a formal audit or guarantee security."}
          </span>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex shrink-0 items-center gap-1 font-medium text-accent hover:underline focus:outline-none"
        >
          {isExpanded ? (
            <>
              <span>Less</span>
              <ChevronDown className="h-3.5 w-3.5" />
            </>
          ) : (
            <>
              <span>Full Notice</span>
              <ChevronUp className="h-3.5 w-3.5" />
            </>
          )}
        </button>
      </div>
    </footer>
  );
}


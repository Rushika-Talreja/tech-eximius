import Link from "next/link";
import { FolderGit2, Plus, ShieldCheck, ArrowRight } from "lucide-react";

export default function ProjectsPage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Projects</h1>
          <p className="mt-1 text-sm text-text-muted">
            Manage smart contract codebases and advisory security audits.
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-black transition-opacity hover:opacity-90">
          <Plus className="h-4 w-4" />
          <span>New Project</span>
        </button>
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {/* Placeholder starter project card */}
        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm transition hover:border-accent/40">
          <div className="flex items-center justify-between">
            <div className="rounded-lg bg-surface-2 p-2.5 text-accent">
              <FolderGit2 className="h-5 w-5" />
            </div>
            <span className="rounded-full bg-ok/10 px-2.5 py-0.5 text-xs font-medium text-ok">
              Active
            </span>
          </div>

          <h3 className="mt-4 text-lg font-semibold text-text">DeFi Vault V1</h3>
          <p className="mt-1 line-clamp-2 text-sm text-text-muted">
            ERC-4626 multi-asset yield vault smart contracts.
          </p>

          <div className="mt-6 flex items-center justify-between border-t border-border pt-4 text-xs text-text-muted">
            <span className="flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-accent" />
              1 audit run
            </span>
            <Link
              href="/projects/demo-vault"
              className="flex items-center gap-1 font-medium text-accent hover:underline"
            >
              <span>View Audits</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}


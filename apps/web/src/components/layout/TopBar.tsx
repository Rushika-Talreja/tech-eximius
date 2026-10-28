import Link from "next/link";
import { Shield, FolderGit2, KeyRound } from "lucide-react";

export function TopBar() {
  return (
    <header className="sticky top-0 z-40 flex h-14 w-full items-center justify-between border-b border-border bg-surface/90 px-6 backdrop-blur">
      <div className="flex items-center gap-6">
        <Link href="/projects" className="flex items-center gap-2 font-semibold text-text">
          <Shield className="h-5 w-5 text-accent" />
          <span className="tracking-tight">DeFi Contract Auditor</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm text-text-muted">
          <Link
            href="/projects"
            className="flex items-center gap-1.5 transition-colors hover:text-text"
          >
            <FolderGit2 className="h-4 w-4" />
            <span>Projects</span>
          </Link>
          <Link
            href="/settings/api-keys"
            className="flex items-center gap-1.5 transition-colors hover:text-text"
          >
            <KeyRound className="h-4 w-4" />
            <span>API Keys</span>
          </Link>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <div className="h-2 w-2 rounded-full bg-ok" title="Backend connected" />
        <span className="text-xs text-text-muted">v0.1.0-alpha</span>
      </div>
    </header>
  );
}


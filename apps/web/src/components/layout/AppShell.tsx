import { ReactNode } from "react";
import { TopBar } from "./TopBar";
import { DisclaimerBanner } from "./DisclaimerBanner";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <TopBar />
      <main className="flex-1 overflow-x-hidden">{children}</main>
      <DisclaimerBanner />
    </div>
  );
}


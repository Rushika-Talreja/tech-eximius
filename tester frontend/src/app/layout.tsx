import type { Metadata } from "next";
import { ConsoleProvider } from "../lib/store";
import { Layout } from "../components/Layout";

export const metadata: Metadata = {
  title: "DeFi Auditor - Test Console",
  description: "Internal testing and backend verification console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0, backgroundColor: "#fff", color: "#333" }}>
        <ConsoleProvider>
          <Layout>{children}</Layout>
        </ConsoleProvider>
      </body>
    </html>
  );
}


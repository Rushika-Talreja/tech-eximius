"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export interface RequestLogEntry {
  id: string;
  timestamp: string;
  method: string;
  path: string;
  status: number;
  durationMs: number;
  requestId: string;
  requestHeaders: Record<string, string>;
  requestBody?: any;
  responseHeaders: Record<string, string>;
  responseBody?: any;
  isNotImplemented?: boolean;
}

export type AuthMode = "user_a" | "user_b" | "api_key" | "none";

interface ConsoleContextType {
  authMode: AuthMode;
  setAuthMode: (mode: AuthMode) => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  requestLogs: RequestLogEntry[];
  addLogEntry: (entry: RequestLogEntry) => void;
  clearLogs: () => void;
  showRawJson: boolean;
  setShowRawJson: (show: boolean) => void;
  isDrawerOpen: boolean;
  setIsDrawerOpen: (open: boolean) => void;
}

const ConsoleContext = createContext<ConsoleContextType | null>(null);

export function ConsoleProvider({ children }: { children: React.ReactNode }) {
  const [authMode, setAuthMode] = useState<AuthMode>("user_a");
  const [apiKey, setApiKey] = useState<string>("");
  const [requestLogs, setRequestLogs] = useState<RequestLogEntry[]>([]);
  const [showRawJson, setShowRawJson] = useState<boolean>(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const addLogEntry = (entry: RequestLogEntry) => {
    setRequestLogs((prev) => [entry, ...prev.slice(0, 99)]); // keep last 100
  };

  const clearLogs = () => {
    setRequestLogs([]);
  };

  return (
    <ConsoleContext.Provider
      value={{
        authMode,
        setAuthMode,
        apiKey,
        setApiKey,
        requestLogs,
        addLogEntry,
        clearLogs,
        showRawJson,
        setShowRawJson,
        isDrawerOpen,
        setIsDrawerOpen,
      }}
    >
      {children}
    </ConsoleContext.Provider>
  );
}

export function useConsole() {
  const context = useContext(ConsoleContext);
  if (!context) {
    throw new Error("useConsole must be used within ConsoleProvider");
  }
  return context;
}


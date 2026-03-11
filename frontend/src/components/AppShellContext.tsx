import { createContext, type ReactNode, useContext } from "react";

interface AppShellContextValue {
  closeSearchModal: () => void;
  closeUploadModal: () => void;
  openSearchModal: () => void;
  openUploadModal: () => void;
}

const AppShellContext = createContext<AppShellContextValue | null>(null);

export function AppShellProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: AppShellContextValue;
}) {
  return (
    <AppShellContext.Provider value={value}>
      {children}
    </AppShellContext.Provider>
  );
}

export function useAppShell(): AppShellContextValue {
  const context = useContext(AppShellContext);

  if (!context) {
    throw new Error("useAppShell must be used within an AppShellProvider");
  }

  return context;
}

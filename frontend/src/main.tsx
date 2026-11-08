import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./features/auth/AuthContext";
import { AppRoutes } from "./app/routes";
import "./App.css";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { installGlobalDiagnostics } from "./lib/diagnostics";

const disposeDiagnostics = installGlobalDiagnostics();
if (import.meta.hot) import.meta.hot.dispose(disposeDiagnostics);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Missing #root element");

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary><BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter></ErrorBoundary>
  </StrictMode>,
);

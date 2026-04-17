import { useEffect, useState } from "react";
import { api } from "./api/client";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { VaultBrowser } from "./pages/VaultBrowser";
import { Admin } from "./pages/Admin";
import { FileHistory } from "./pages/FileHistory";
import { ShareView } from "./pages/ShareView";
import { Billing } from "./pages/Billing";
import "./App.css";

type Page = "dashboard" | "vault" | "admin" | "history" | "share" | "billing";

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedVaultId, setSelectedVaultId] = useState("");
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [shareToken, setShareToken] = useState("");

  useEffect(() => {
    // Check for share token in URL (e.g. /share/<token>)
    const pathParts = window.location.pathname.split("/");
    const shareIdx = pathParts.indexOf("share");
    if (shareIdx !== -1 && pathParts[shareIdx + 1]) {
      setShareToken(pathParts[shareIdx + 1]);
      setPage("share");
      return;
    }

    api.loadTokens();
    setAuthenticated(api.isAuthenticated);
  }, []);

  function handleLogin() {
    setAuthenticated(true);
    setPage("dashboard");
  }

  function handleLogout() {
    api.clearTokens();
    setAuthenticated(false);
    setPage("dashboard");
  }

  function navigateToHistory(vaultId: string, filePath: string) {
    setSelectedVaultId(vaultId);
    setSelectedFilePath(filePath);
    setPage("history");
  }

  // Share view is public — no auth required
  if (page === "share" && shareToken) {
    return <ShareView token={shareToken} />;
  }

  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-brand" onClick={() => setPage("dashboard")}>
          Obsidian Sync
        </div>
        <div className="nav-links">
          <button
            className={page === "dashboard" ? "active" : ""}
            onClick={() => setPage("dashboard")}
          >
            Vaults
          </button>
          <button
            className={page === "billing" ? "active" : ""}
            onClick={() => setPage("billing")}
          >
            Billing
          </button>
          <button
            className={page === "admin" ? "active" : ""}
            onClick={() => setPage("admin")}
          >
            Admin
          </button>
          <button onClick={handleLogout}>Logout</button>
        </div>
      </nav>

      <main className="content">
        {page === "dashboard" && (
          <Dashboard
            onSelectVault={(id) => {
              setSelectedVaultId(id);
              setPage("vault");
            }}
          />
        )}
        {page === "vault" && selectedVaultId && (
          <VaultBrowser
            vaultId={selectedVaultId}
            onBack={() => setPage("dashboard")}
            onViewHistory={(filePath) =>
              navigateToHistory(selectedVaultId, filePath)
            }
          />
        )}
        {page === "history" && selectedVaultId && selectedFilePath && (
          <FileHistory
            vaultId={selectedVaultId}
            filePath={selectedFilePath}
            onBack={() => setPage("vault")}
          />
        )}
        {page === "billing" && <Billing />}
        {page === "admin" && <Admin />}
      </main>
    </div>
  );
}

export default App;

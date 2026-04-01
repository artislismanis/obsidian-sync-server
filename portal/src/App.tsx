import { useEffect, useState } from "react";
import { api } from "./api/client";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { VaultBrowser } from "./pages/VaultBrowser";
import { Admin } from "./pages/Admin";
import "./App.css";

type Page = "dashboard" | "vault" | "admin";

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedVaultId, setSelectedVaultId] = useState("");

  useEffect(() => {
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
          />
        )}
        {page === "admin" && <Admin />}
      </main>
    </div>
  );
}

export default App;

import { useEffect, useState } from "react";
import { api, type VaultInfo } from "../api/client";

interface DashboardProps {
  onSelectVault: (vaultId: string) => void;
}

export function Dashboard({ onSelectVault }: DashboardProps) {
  const [vaults, setVaults] = useState<VaultInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getVaults().then((data) => {
      setVaults(data.vaults);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="loading">Loading vaults...</div>;

  return (
    <div className="dashboard">
      <h1>Your Vaults</h1>
      <div className="vault-grid">
        {vaults.map((vault) => (
          <div
            key={vault.id}
            className="vault-card"
            onClick={() => onSelectVault(vault.id)}
          >
            <h3>{vault.name}</h3>
            <div className="vault-meta">
              <span className="badge">{vault.storage_backend}</span>
              {vault.encrypted && <span className="badge encrypted">Encrypted</span>}
              <span className="badge">{vault.sync_mode}</span>
            </div>
            <p className="vault-date">Created: {new Date(vault.created_at).toLocaleDateString()}</p>
          </div>
        ))}
        {vaults.length === 0 && (
          <p className="empty">No vaults yet. Create one from the Obsidian plugin or CLI.</p>
        )}
      </div>
    </div>
  );
}

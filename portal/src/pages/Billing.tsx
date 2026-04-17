import { useEffect, useState } from "react";
import { api, type SubscriptionInfo } from "../api/client";

export function Billing() {
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(
    null
  );
  const [selfHosted, setSelfHosted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    api
      .getSubscription()
      .then((data) => {
        setSubscription(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Unknown error";
        // A 404 means the server is running in self-hosted mode
        if (message.includes("404") || message.includes("Not Found")) {
          setSelfHosted(true);
        } else {
          setError(message);
        }
        setLoading(false);
      });
  }, []);

  async function handleUpgrade() {
    setActionLoading(true);
    try {
      const data = await api.createCheckout();
      window.location.href = data.checkout_url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create checkout");
      setActionLoading(false);
    }
  }

  async function handleManage() {
    setActionLoading(true);
    try {
      const data = await api.createPortalSession();
      window.location.href = data.portal_url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to open billing portal");
      setActionLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading billing info...</div>;

  if (selfHosted) {
    return (
      <div className="billing">
        <h1>Billing</h1>
        <div className="billing-card">
          <h2>Self-hosted mode</h2>
          <p>All features are unlocked. No subscription required.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="billing">
        <h1>Billing</h1>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!subscription) return null;

  return (
    <div className="billing">
      <h1>Billing</h1>
      <div className="billing-card">
        <h2>
          Current Plan: <span className="plan-name">{subscription.tier}</span>
        </h2>
        <p className="plan-status">
          Status: <strong>{subscription.status}</strong>
        </p>
        {subscription.current_period_end && (
          <p className="plan-period">
            Current period ends:{" "}
            {new Date(subscription.current_period_end).toLocaleDateString()}
          </p>
        )}
      </div>

      <div className="billing-entitlements">
        <h3>Entitlements</h3>
        <ul>
          <li>
            Vaults: {subscription.entitlements.vault_count} /{" "}
            {subscription.entitlements.max_vaults}
          </li>
          <li>
            Storage: {formatBytes(subscription.entitlements.storage_used)} /{" "}
            {formatBytes(subscription.entitlements.max_storage_bytes)}
          </li>
          <li>
            Collaborators per vault:{" "}
            {subscription.entitlements.max_collaborators}
          </li>
          <li>
            Version history: {subscription.entitlements.version_history_days}{" "}
            days
          </li>
        </ul>
      </div>

      <div className="billing-actions">
        <button
          className="upgrade-btn"
          onClick={handleUpgrade}
          disabled={actionLoading}
        >
          {actionLoading ? "Loading..." : "Upgrade"}
        </button>
        <button
          className="manage-btn"
          onClick={handleManage}
          disabled={actionLoading}
        >
          {actionLoading ? "Loading..." : "Manage Subscription"}
        </button>
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

const API_BASE = import.meta.env.VITE_API_URL || "";

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

class APIClient {
  private accessToken = "";
  private refreshToken = "";

  setTokens(access: string, refresh: string): void {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  }

  loadTokens(): void {
    this.accessToken = localStorage.getItem("access_token") || "";
    this.refreshToken = localStorage.getItem("refresh_token") || "";
  }

  clearTokens(): void {
    this.accessToken = "";
    this.refreshToken = "";
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  get isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {} } = options;

    const fetchOptions: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(this.accessToken
          ? { Authorization: `Bearer ${this.accessToken}` }
          : {}),
        ...headers,
      },
    };

    if (body) {
      fetchOptions.body = JSON.stringify(body);
    }

    let resp = await fetch(`${API_BASE}${path}`, fetchOptions);

    // Auto-refresh on 401
    if (resp.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        (fetchOptions.headers as Record<string, string>).Authorization =
          `Bearer ${this.accessToken}`;
        resp = await fetch(`${API_BASE}${path}`, fetchOptions);
      }
    }

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(
        (error as Record<string, string>).detail || `HTTP ${resp.status}`
      );
    }

    if (resp.status === 204) return {} as T;
    return resp.json() as Promise<T>;
  }

  private async refreshAccessToken(): Promise<boolean> {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
      if (resp.ok) {
        const data = (await resp.json()) as {
          access_token: string;
          refresh_token: string;
        };
        this.setTokens(data.access_token, data.refresh_token);
        return true;
      }
    } catch {
      // refresh failed
    }
    this.clearTokens();
    return false;
  }

  // --- Convenience methods ---

  async login(
    username: string,
    password: string
  ): Promise<{ access_token: string; refresh_token: string }> {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
    }>("/api/v1/auth/login", {
      method: "POST",
      body: { username, password },
    });
    this.setTokens(data.access_token, data.refresh_token);
    return data;
  }

  async getVaults(): Promise<{ vaults: VaultInfo[]; total: number }> {
    return this.request("/api/v1/vaults");
  }

  async getVaultFiles(
    vaultId: string
  ): Promise<{ files: FileInfo[]; vault_version: number }> {
    return this.request(`/api/v1/vaults/${vaultId}/files`);
  }

  async getFileContent(
    vaultId: string,
    path: string
  ): Promise<{ content: string; version: number; path: string }> {
    return this.request(
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}`
    );
  }

  async getHealth(): Promise<{ status: string; version: string; mode: string }> {
    return this.request("/api/v1/health");
  }

  async getFileHistory(
    vaultId: string,
    path: string
  ): Promise<{ versions: FileVersionInfo[] }> {
    return this.request(
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}/history`
    );
  }

  async restoreFileVersion(
    vaultId: string,
    path: string,
    version: number
  ): Promise<void> {
    await this.request(
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}/restore`,
      { method: "POST", body: { version } }
    );
  }

  async getShareLink(token: string, password?: string): Promise<ShareData> {
    const query = password
      ? `?password=${encodeURIComponent(password)}`
      : "";
    return this.request(`/api/v1/share/${token}${query}`);
  }

  async getSubscription(): Promise<SubscriptionInfo> {
    return this.request("/api/v1/billing/subscription");
  }

  async createCheckout(): Promise<{ checkout_url: string }> {
    return this.request("/api/v1/billing/checkout", { method: "POST" });
  }

  async createPortalSession(): Promise<{ portal_url: string }> {
    return this.request("/api/v1/billing/portal", { method: "POST" });
  }
}

export interface VaultInfo {
  id: string;
  name: string;
  owner_id: string;
  storage_backend: string;
  encrypted: boolean;
  sync_mode: string;
  obsidian_config_sync: string;
  created_at: string;
  updated_at: string;
}

export interface FileInfo {
  path: string;
  version: number;
  content_hash: string;
  size_bytes: number;
  author_id: string;
  created_at: string;
}

export interface FileVersionInfo {
  version: number;
  author_id: string;
  created_at: string;
  size_bytes: number;
  content_hash: string;
}

export interface ShareData {
  file_path: string;
  content: string;
  shared_by: string;
  created_at: string;
}

export interface SubscriptionInfo {
  tier: string;
  status: string;
  current_period_end: string | null;
  entitlements: {
    vault_count: number;
    max_vaults: number;
    storage_used: number;
    max_storage_bytes: number;
    max_collaborators: number;
    version_history_days: number;
  };
}

export const api = new APIClient();

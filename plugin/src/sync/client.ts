import { requestUrl, RequestUrlParam } from "obsidian";
import { getSyncProfile } from "./platform";
import { arrayBufferToBase64, base64ToArrayBuffer, sha256Hex } from "../utils/encoding";

export interface SyncServerConfig {
  serverUrl: string;
  accessToken: string;
  refreshToken: string;
  deviceId?: string;
  deviceName?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface VaultInfo {
  id: string;
  name: string;
  owner_id: string;
  storage_backend: string;
  encrypted: boolean;
  sync_mode: string;
}

export interface FileInfo {
  path: string;
  version: number;
  content_hash: string;
  size_bytes: number;
  author_id: string;
}

export type WSMessageHandler = (data: Record<string, unknown>) => void;

/**
 * HTTP + WebSocket client for the sync server.
 * Uses Obsidian's requestUrl (works on mobile).
 */
export class SyncClient {
  private config: SyncServerConfig;
  private ws: WebSocket | null = null;
  private wsHandlers: Map<string, WSMessageHandler[]> = new Map();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;

  constructor(config: SyncServerConfig) {
    this.config = config;
  }

  get serverUrl(): string {
    return this.config.serverUrl.replace(/\/$/, "");
  }

  // --- HTTP methods ---

  private async request(
    method: string,
    path: string,
    body?: unknown
  ): Promise<Record<string, unknown>> {
    const params: RequestUrlParam = {
      url: `${this.serverUrl}${path}`,
      method,
      headers: {
        Authorization: `Bearer ${this.config.accessToken}`,
        "Content-Type": "application/json",
      },
    };
    if (body) {
      params.body = JSON.stringify(body);
    }

    const response = await requestUrl(params);

    // Auto-refresh token on 401
    if (response.status === 401) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        params.headers = {
          ...params.headers,
          Authorization: `Bearer ${this.config.accessToken}`,
        };
        const retry = await requestUrl(params);
        return retry.json as Record<string, unknown>;
      }
    }

    if (response.status >= 400) {
      throw new Error(
        `API error ${response.status}: ${JSON.stringify(response.json)}`
      );
    }

    return response.json as Record<string, unknown>;
  }

  async refreshToken(): Promise<boolean> {
    try {
      const resp = await requestUrl({
        url: `${this.serverUrl}/api/v1/auth/refresh`,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.config.refreshToken }),
      });
      if (resp.status === 200) {
        const data = resp.json as TokenResponse;
        this.config.accessToken = data.access_token;
        this.config.refreshToken = data.refresh_token;
        return true;
      }
    } catch {
      // Refresh failed
    }
    return false;
  }

  async login(username: string, password: string): Promise<TokenResponse> {
    const resp = await requestUrl({
      url: `${this.serverUrl}/api/v1/auth/login`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = resp.json as TokenResponse;
    this.config.accessToken = data.access_token;
    this.config.refreshToken = data.refresh_token;
    return data;
  }

  async listVaults(): Promise<VaultInfo[]> {
    const data = await this.request("GET", "/api/v1/vaults");
    return (data.vaults as VaultInfo[]) || [];
  }

  async createVault(name: string): Promise<VaultInfo> {
    const data = await this.request("POST", "/api/v1/vaults", { name });
    return data as unknown as VaultInfo;
  }

  async listFiles(
    vaultId: string
  ): Promise<{ files: FileInfo[]; vault_version: number }> {
    const data = await this.request(
      "GET",
      `/api/v1/vaults/${vaultId}/files`
    );
    return data as { files: FileInfo[]; vault_version: number };
  }

  async uploadFile(
    vaultId: string,
    path: string,
    content: ArrayBuffer,
    version: number
  ): Promise<FileInfo> {
    const b64 = arrayBufferToBase64(content);
    const data = await this.request(
      "PUT",
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}`,
      {
        path,
        content: b64,
        version,
        content_hash: await sha256Hex(content),
      }
    );
    return data as unknown as FileInfo;
  }

  async downloadFile(
    vaultId: string,
    path: string
  ): Promise<{ content: ArrayBuffer; version: number }> {
    const data = await this.request(
      "GET",
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}`
    );
    const b64 = data.content as string;
    const content = base64ToArrayBuffer(b64);
    return { content, version: data.version as number };
  }

  async deleteFile(vaultId: string, path: string): Promise<void> {
    await this.request(
      "DELETE",
      `/api/v1/vaults/${vaultId}/files/${encodeURIComponent(path)}`
    );
  }

  async getDeletedFiles(
    vaultId: string
  ): Promise<{ files: Record<string, unknown>[] }> {
    return this.request("GET", `/api/v1/vaults/${vaultId}/deleted-files`) as Promise<{
      files: Record<string, unknown>[];
    }>;
  }

  async restoreDeletedFile(vaultId: string, path: string): Promise<void> {
    await this.request("POST", `/api/v1/vaults/${vaultId}/deleted-files/restore`, {
      path,
    });
  }

  async getVaultStorageUsed(vaultId: string): Promise<number> {
    const data = await this.request(
      "GET",
      `/api/v1/vaults/${vaultId}`
    );
    return (data as Record<string, unknown>).storage_used_bytes as number || 0;
  }

  // --- WebSocket ---

  connectWebSocket(vaultId: string): void {
    this.shouldReconnect = true;
    this._connectWS(vaultId);
  }

  private _connectWS(vaultId: string): void {
    const params = new URLSearchParams({
      token: this.config.accessToken,
      device_id: this.config.deviceId || "",
      device_name: this.config.deviceName || "",
    });
    const wsUrl = this.serverUrl
      .replace(/^http/, "ws")
      .concat(`/api/v1/sync/${vaultId}?${params.toString()}`);

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<
          string,
          unknown
        >;
        const msgType = data.type as string;
        const handlers = this.wsHandlers.get(msgType) || [];
        for (const handler of handlers) {
          handler(data);
        }
        // Also fire wildcard handlers
        const wildcardHandlers = this.wsHandlers.get("*") || [];
        for (const handler of wildcardHandlers) {
          handler(data);
        }
      } catch {
        // Ignore parse errors
      }
    };

    this.ws.onclose = () => {
      if (this.shouldReconnect) {
        this._scheduleReconnect(vaultId);
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  private _scheduleReconnect(vaultId: string): void {
    const profile = getSyncProfile();
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempt),
      profile.wsReconnectMaxDelayMs
    );
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => this._connectWS(vaultId), delay);
  }

  disconnectWebSocket(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  onMessage(type: string, handler: WSMessageHandler): void {
    if (!this.wsHandlers.has(type)) {
      this.wsHandlers.set(type, []);
    }
    this.wsHandlers.get(type)!.push(handler);
  }

  sendMessage(data: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  updateTokens(accessToken: string, refreshToken: string): void {
    this.config.accessToken = accessToken;
    this.config.refreshToken = refreshToken;
  }
}

import { TFile, TAbstractFile, Vault, Notice } from "obsidian";
import { SyncClient } from "./client";
import { SyncQueue, QueuedChange } from "./queue";
import { conflictPath } from "./conflict";
import { getSyncProfile, SyncProfile, isMobile } from "./platform";
import { debounce } from "../utils/debounce";
import { arrayBufferToBase64, base64ToArrayBuffer, sha256Hex } from "../utils/encoding";

export interface SyncEngineConfig {
  vaultId: string;
  client: SyncClient;
  vault: Vault;
}

interface FileVersionMap {
  [path: string]: number;
}

/**
 * Core sync engine — orchestrates on-save sync between Obsidian and the server.
 * Handles file watching, upload/download, offline queuing, and conflict resolution.
 */
export class SyncEngine {
  private config: SyncEngineConfig;
  private queue: SyncQueue;
  private profile: SyncProfile;
  private versions: FileVersionMap = {};
  private syncing = false;
  private debouncedSync: ReturnType<typeof debounce>;
  private processing = false;

  constructor(config: SyncEngineConfig) {
    this.config = config;
    this.queue = new SyncQueue();
    this.profile = getSyncProfile();
    this.debouncedSync = debounce(
      () => this.processQueue(),
      this.profile.debounceMs
    );
  }

  /**
   * Start the sync engine: do initial sync, set up file watchers, connect WebSocket.
   */
  async start(): Promise<void> {
    // Initial pull — get current server state
    try {
      const serverFiles = await this.config.client.listFiles(
        this.config.vaultId
      );
      for (const f of serverFiles.files) {
        this.versions[f.path] = f.version;
      }
    } catch {
      new Notice("Sync: Failed to connect to server");
    }

    // Connect WebSocket for real-time notifications
    this.config.client.connectWebSocket(this.config.vaultId);
    this.config.client.onMessage("file_changed", (data) =>
      this.handleRemoteChange(data)
    );
    this.config.client.onMessage("file_deleted", (data) =>
      this.handleRemoteDelete(data)
    );
    this.config.client.onMessage("file_renamed", (data) =>
      this.handleRemoteRename(data)
    );
    this.config.client.onMessage("conflict", (data) =>
      this.handleConflict(data)
    );
  }

  stop(): void {
    this.config.client.disconnectWebSocket();
    this.debouncedSync.cancel();
  }

  // --- Local file events ---

  onFileModify(file: TAbstractFile): void {
    if (!(file instanceof TFile)) return;
    if (this.shouldSkipFile(file)) return;

    this.queue.enqueue({
      type: this.versions[file.path] ? "update" : "create",
      path: file.path,
      timestamp: Date.now(),
    });
    this.debouncedSync();
  }

  onFileCreate(file: TAbstractFile): void {
    if (!(file instanceof TFile)) return;
    if (this.shouldSkipFile(file)) return;

    this.queue.enqueue({
      type: "create",
      path: file.path,
      timestamp: Date.now(),
    });
    this.debouncedSync();
  }

  onFileDelete(file: TAbstractFile): void {
    if (!(file instanceof TFile)) return;

    this.queue.enqueue({
      type: "delete",
      path: file.path,
      timestamp: Date.now(),
    });
    this.debouncedSync();
  }

  onFileRename(file: TAbstractFile, oldPath: string): void {
    if (!(file instanceof TFile)) return;

    this.queue.enqueue({
      type: "rename",
      path: oldPath,
      newPath: file.path,
      timestamp: Date.now(),
    });
    this.debouncedSync();
  }

  // --- Queue processing ---

  private async processQueue(): Promise<void> {
    if (this.processing) return;
    this.processing = true;

    let concurrent = 0;

    try {
      while (!this.queue.isEmpty()) {
        if (concurrent >= this.profile.maxConcurrentUploads) {
          // Wait briefly then retry
          await sleep(100);
          continue;
        }

        const change = this.queue.dequeue();
        if (!change) break;

        concurrent++;
        try {
          await this.processChange(change);
        } catch {
          // Re-queue on failure (will retry on next debounce)
          this.queue.enqueue(change);
          break; // Stop processing — likely offline
        } finally {
          concurrent--;
        }
      }
    } finally {
      this.processing = false;
    }
  }

  private async processChange(change: QueuedChange): Promise<void> {
    const { client, vaultId, vault } = this.config;

    switch (change.type) {
      case "create":
      case "update": {
        const file = vault.getAbstractFileByPath(change.path);
        if (!(file instanceof TFile)) return;

        // Mobile: skip large files unless on WiFi
        if (
          isMobile() &&
          file.stat.size > this.profile.maxAutoSyncBytes
        ) {
          new Notice(`Sync: ${file.name} too large for mobile sync`);
          return;
        }

        const content = await vault.readBinary(file);
        const version = this.versions[change.path] || 0;

        if (client.isConnected) {
          // Use WebSocket for connected sync
          const b64 = arrayBufferToBase64(content);
          const hash = await sha256Hex(content);
          client.sendMessage({
            type: "file_save",
            path: change.path,
            content: b64,
            version,
            content_hash: hash,
          });
        } else {
          // Fall back to REST
          const result = await client.uploadFile(
            vaultId,
            change.path,
            content,
            version
          );
          this.versions[change.path] = result.version;
        }
        break;
      }

      case "delete": {
        if (client.isConnected) {
          client.sendMessage({
            type: "file_delete",
            path: change.path,
            version: this.versions[change.path] || 0,
          });
        } else {
          await client.deleteFile(vaultId, change.path);
        }
        delete this.versions[change.path];
        break;
      }

      case "rename": {
        if (client.isConnected && change.newPath) {
          client.sendMessage({
            type: "file_rename",
            old_path: change.path,
            new_path: change.newPath,
            version: this.versions[change.path] || 0,
          });
          if (change.newPath) {
            this.versions[change.newPath] = this.versions[change.path] || 0;
          }
          delete this.versions[change.path];
        }
        break;
      }
    }
  }

  // --- Remote event handlers ---

  private async handleRemoteChange(
    data: Record<string, unknown>
  ): Promise<void> {
    const path = data.path as string;
    const version = data.version as number;
    const contentB64 = data.content as string;

    if (!path || !contentB64) return;

    this.versions[path] = version;

    const content = base64ToArrayBuffer(contentB64);
    const existing = this.config.vault.getAbstractFileByPath(path);

    if (existing instanceof TFile) {
      await this.config.vault.modifyBinary(existing, content);
    } else {
      await this.config.vault.createBinary(path, content);
    }
  }

  private async handleRemoteDelete(
    data: Record<string, unknown>
  ): Promise<void> {
    const path = data.path as string;
    if (!path) return;

    delete this.versions[path];

    const file = this.config.vault.getAbstractFileByPath(path);
    if (file instanceof TFile) {
      await this.config.vault.delete(file);
    }
  }

  private async handleRemoteRename(
    data: Record<string, unknown>
  ): Promise<void> {
    const oldPath = data.old_path as string;
    const newPath = data.new_path as string;
    if (!oldPath || !newPath) return;

    this.versions[newPath] = this.versions[oldPath] || 0;
    delete this.versions[oldPath];

    const file = this.config.vault.getAbstractFileByPath(oldPath);
    if (file instanceof TFile) {
      await this.config.vault.rename(file, newPath);
    }
  }

  private async handleConflict(
    data: Record<string, unknown>
  ): Promise<void> {
    const path = data.path as string;
    if (!path) return;

    const file = this.config.vault.getAbstractFileByPath(path);
    if (!(file instanceof TFile)) return;

    // Save local version as conflict file
    const content = await this.config.vault.readBinary(file);
    const cPath = conflictPath(path);
    await this.config.vault.createBinary(cPath, content);

    new Notice(
      `Sync conflict: ${path}\nYour version saved as ${cPath}`
    );

    // Pull server version
    try {
      const server = await this.config.client.downloadFile(
        this.config.vaultId,
        path
      );
      await this.config.vault.modifyBinary(file, server.content);
      this.versions[path] = server.version;
    } catch {
      // Will retry on next sync
    }
  }

  // --- Helpers ---

  private shouldSkipFile(file: TFile): boolean {
    // Skip hidden files and conflict files
    if (file.path.startsWith(".")) return true;
    if (file.path.includes(".conflict-")) return true;
    return false;
  }

  get pendingChanges(): number {
    return this.queue.length;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

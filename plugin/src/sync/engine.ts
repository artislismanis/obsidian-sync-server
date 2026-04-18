import { TFile, TAbstractFile, Vault, Notice } from "obsidian";
import { SyncClient } from "./client";
import { SyncQueue, QueuedChange } from "./queue";
import { conflictPath } from "./conflict";
import { getSyncProfile, SyncProfile, isMobile } from "./platform";
import { debounce } from "../utils/debounce";
import { arrayBufferToBase64, base64ToArrayBuffer, sha256Hex } from "../utils/encoding";

export type ConflictStrategy = "keep-both" | "server-wins" | "local-wins";

export interface SyncEngineConfig {
  vaultId: string;
  client: SyncClient;
  vault: Vault;
  conflictStrategy?: ConflictStrategy;
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
  private _syncLog: string[] = [];
  private _stats = { uploaded: 0, downloaded: 0, deleted: 0 };

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
   * Start the sync engine: do full bidirectional sync, then set up watchers.
   */
  async start(): Promise<void> {
    try {
      await this.initialSync();
    } catch {
      this.log("Failed to connect to server");
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

  /**
   * Full bidirectional sync: compare local files against server,
   * pull new/changed server files, push new/changed local files.
   */
  private async initialSync(): Promise<void> {
    const serverData = await this.config.client.listFiles(
      this.config.vaultId
    );
    const serverFiles = new Map<string, { version: number; content_hash: string }>();
    for (const f of serverData.files) {
      serverFiles.set(f.path, { version: f.version, content_hash: f.content_hash });
      this.versions[f.path] = f.version;
    }

    // Get all local files
    const localFiles = this.config.vault.getFiles();
    const localPaths = new Set<string>();
    let pulled = 0;
    let pushed = 0;

    // Pull files that exist on server but not locally, or are newer
    for (const [path, info] of serverFiles) {
      const localFile = this.config.vault.getAbstractFileByPath(path);
      if (!(localFile instanceof TFile)) {
        // File exists on server but not locally — pull it
        try {
          const { content } = await this.config.client.downloadFile(
            this.config.vaultId, path
          );
          await this.config.vault.createBinary(path, content);
          this.log(`↓ ${path} (v${info.version}) — new from server`);
          this._stats.downloaded++;
          pulled++;
        } catch {
          this.log(`✗ Failed to pull ${path}`);
        }
      }
    }

    // Push local files that don't exist on server or have changed
    for (const file of localFiles) {
      if (this.shouldSkipFile(file)) continue;
      localPaths.add(file.path);

      const serverInfo = serverFiles.get(file.path);

      if (!serverInfo) {
        // File exists locally but not on server — push it
        this.queue.enqueue({
          type: "create",
          path: file.path,
          timestamp: Date.now(),
        });
        pushed++;
      } else {
        // File exists on both — check if local is different by hash
        try {
          const content = await this.config.vault.readBinary(file);
          const localHash = await sha256Hex(content);
          if (localHash !== serverInfo.content_hash) {
            this.queue.enqueue({
              type: "update",
              path: file.path,
              timestamp: Date.now(),
            });
            pushed++;
          }
        } catch {
          // skip unreadable files
        }
      }
    }

    // Process the push queue
    if (!this.queue.isEmpty()) {
      await this.processQueue();
    }

    const total = serverFiles.size + pushed;
    this.log(`Initial sync: ${pulled} pulled, ${pushed} pushed, ${serverFiles.size} on server`);
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
          const b64 = arrayBufferToBase64(content);
          const hash = await sha256Hex(content);
          client.sendMessage({
            type: "file_save",
            path: change.path,
            content: b64,
            version,
            content_hash: hash,
          });
          this.log(`↑ ${change.path} (v${version + 1})`);
          this._stats.uploaded++;
        } else {
          // Fall back to REST
          const result = await client.uploadFile(
            vaultId,
            change.path,
            content,
            version
          );
          this.versions[change.path] = result.version;
          this.log(`↑ ${change.path} (v${result.version}) via REST`);
          this._stats.uploaded++;
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
      this.log(`↓ ${path} updated (v${version})`);
      this._stats.downloaded++;
    } else {
      await this.config.vault.createBinary(path, content);
      this.log(`↓ ${path} created (v${version})`);
      this._stats.downloaded++;
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

    const strategy = this.config.conflictStrategy || "keep-both";
    const file = this.config.vault.getAbstractFileByPath(path);
    if (!(file instanceof TFile)) return;

    if (strategy === "local-wins") {
      const content = await this.config.vault.readBinary(file);
      const b64 = arrayBufferToBase64(content);
      const hash = await sha256Hex(content);
      this.config.client.sendMessage({
        type: "file_save",
        path,
        content: b64,
        version: 0,
        content_hash: hash,
      });
      this.log(`⚡ ${path} — conflict resolved: local wins`);
      this._stats.uploaded++;
      new Notice(`Sync conflict: ${path} — local version kept`);
      return;
    }

    if (strategy === "server-wins") {
      try {
        const server = await this.config.client.downloadFile(
          this.config.vaultId, path
        );
        await this.config.vault.modifyBinary(file, server.content);
        this.versions[path] = server.version;
        this.log(`⚡ ${path} — conflict resolved: server wins`);
        this._stats.downloaded++;
        new Notice(`Sync conflict: ${path} — server version kept`);
      } catch {
        // Will retry on next sync
      }
      return;
    }

    // keep-both: save local as conflict file, pull server version
    const content = await this.config.vault.readBinary(file);
    const cPath = conflictPath(path);
    await this.config.vault.createBinary(cPath, content);
    this.log(`⚡ ${path} — conflict: local saved as ${cPath}`);

    try {
      const server = await this.config.client.downloadFile(
        this.config.vaultId, path
      );
      await this.config.vault.modifyBinary(file, server.content);
      this.versions[path] = server.version;
      this._stats.downloaded++;
    } catch {
      // Will retry
    }

    new Notice(`Sync conflict: ${path}\nYour version saved as ${cPath}`);
  }

  // --- Helpers ---

  private shouldSkipFile(file: TFile): boolean {
    if (file.path.startsWith(".")) return true;
    if (file.path.includes(".conflict-")) return true;
    return false;
  }

  private log(msg: string): void {
    const ts = new Date().toLocaleTimeString();
    this._syncLog.push(`[${ts}] ${msg}`);
    if (this._syncLog.length > 100) this._syncLog.shift();
  }

  get pendingChanges(): number {
    return this.queue.length;
  }

  get trackedFileCount(): number {
    return Object.keys(this.versions).length;
  }

  get stats(): { uploaded: number; downloaded: number; deleted: number } {
    return { ...this._stats };
  }

  get syncLog(): string[] {
    return [...this._syncLog];
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

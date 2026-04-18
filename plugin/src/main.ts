import { Platform, Plugin } from "obsidian";
import { SyncSettingTab } from "./settings";
import { SyncClient, SyncServerConfig } from "./sync/client";
import { SyncEngine } from "./sync/engine";
import { SyncStatusBar } from "./ui/status-bar";
import { SyncLogModal } from "./ui/sync-log-modal";
import { FirstSyncModal } from "./ui/first-sync-modal";
import { ConflictResolverModal } from "./ui/conflict-resolver-modal";

interface SyncPluginSettings {
  serverUrl: string;
  accessToken: string;
  refreshToken: string;
  vaultId: string;
  vaultName: string;
  autoSync: boolean;
  conflictStrategy: string;
  syncedVaults: string[];
  deviceId: string;
  deviceName: string;
}

function generateDeviceId(): string {
  const arr = new Uint8Array(16);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

function defaultDeviceName(): string {
  if (Platform.isIosApp) return "iPhone/iPad";
  if (Platform.isAndroidApp) return "Android";
  if (Platform.isMacOS) return "Mac";
  if (Platform.isWin) return "Windows PC";
  if (Platform.isLinux) return "Linux";
  return "Desktop";
}

const DEFAULT_SETTINGS: SyncPluginSettings = {
  serverUrl: "",
  accessToken: "",
  refreshToken: "",
  vaultId: "",
  vaultName: "",
  autoSync: true,
  conflictStrategy: "keep-both",
  syncedVaults: [],
  deviceId: "",
  deviceName: "",
};

export default class ObsidianSyncPlugin extends Plugin {
  settings: SyncPluginSettings = DEFAULT_SETTINGS;
  client: SyncClient | null = null;
  engine: SyncEngine | null = null;
  statusBar: SyncStatusBar | null = null;

  async onload(): Promise<void> {
    await this.loadSettings();

    if (!this.settings.deviceId) {
      this.settings.deviceId = generateDeviceId();
      this.settings.deviceName = defaultDeviceName();
      await this.saveSettings();
    }

    this.addSettingTab(new SyncSettingTab(this.app, this));
    this.statusBar = new SyncStatusBar(this);

    this.addCommand({
      id: "show-sync-log",
      name: "Show sync log",
      callback: () => {
        const logs = this.engine?.syncLog ?? [];
        new SyncLogModal(this.app, logs).open();
      },
    });

    this.addCommand({
      id: "force-sync",
      name: "Force sync now",
      callback: async () => {
        if (this.engine) {
          await this.startSync();
        }
      },
    });

    this.addCommand({
      id: "resolve-conflicts",
      name: "Resolve sync conflicts",
      callback: () => {
        new ConflictResolverModal(this.app, this.app.vault).open();
      },
    });

    if (this.settings.serverUrl && this.settings.accessToken) {
      await this.startSync();
    }
  }

  async onunload(): Promise<void> {
    this.stopSync();
    this.statusBar?.destroy();
    this.statusBar = null;
  }

  async startSync(): Promise<void> {
    if (this.engine) this.stopSync();

    const config: SyncServerConfig = {
      serverUrl: this.settings.serverUrl,
      accessToken: this.settings.accessToken,
      refreshToken: this.settings.refreshToken,
      deviceId: this.settings.deviceId,
      deviceName: this.settings.deviceName,
    };

    this.client = new SyncClient(config);

    if (!this.settings.vaultId) return;

    // First-sync confirmation: show modal on first connection to this vault
    const isFirstSync = !this.settings.syncedVaults.includes(this.settings.vaultId);
    if (isFirstSync) {
      const localFiles = this.app.vault.getFiles().filter(
        (f) => !f.path.startsWith(".") && !f.path.includes(".conflict-")
      );

      let serverFileCount = 0;
      try {
        const serverData = await this.client.listFiles(this.settings.vaultId);
        serverFileCount = serverData.files.length;
      } catch {
        // New vault or unreachable — proceed
      }

      if (localFiles.length > 0 || serverFileCount > 0) {
        const modal = new FirstSyncModal(this.app, localFiles.length, serverFileCount);
        const result = await modal.waitForResult();
        if (!result.confirmed) return;
        this.settings.conflictStrategy = result.strategy;
      }

      this.settings.syncedVaults = [...this.settings.syncedVaults, this.settings.vaultId];
      await this.saveSettings();
    }

    this.engine = new SyncEngine({
      vaultId: this.settings.vaultId,
      client: this.client,
      vault: this.app.vault,
      conflictStrategy: this.settings.conflictStrategy as "keep-both" | "server-wins" | "local-wins",
    });

    this.statusBar?.startMonitoring(this.engine, this.client);

    await this.engine.start();

    // Register file event handlers
    if (this.settings.autoSync) {
      this.registerEvent(
        this.app.vault.on("modify", (file) => this.engine?.onFileModify(file))
      );
      this.registerEvent(
        this.app.vault.on("create", (file) => this.engine?.onFileCreate(file))
      );
      this.registerEvent(
        this.app.vault.on("delete", (file) => this.engine?.onFileDelete(file))
      );
      this.registerEvent(
        this.app.vault.on("rename", (file, oldPath) =>
          this.engine?.onFileRename(file, oldPath)
        )
      );
    }
  }

  stopSync(): void {
    this.engine?.stop();
    this.engine = null;
    this.statusBar?.stopMonitoring();
    this.client = null;
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }
}

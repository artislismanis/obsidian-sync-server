import { Plugin } from "obsidian";
import { SyncSettingTab } from "./settings";
import { SyncClient, SyncServerConfig } from "./sync/client";
import { SyncEngine } from "./sync/engine";
import { SyncStatusBar } from "./ui/status-bar";

interface SyncPluginSettings {
  serverUrl: string;
  accessToken: string;
  refreshToken: string;
  vaultId: string;
  autoSync: boolean;
}

const DEFAULT_SETTINGS: SyncPluginSettings = {
  serverUrl: "",
  accessToken: "",
  refreshToken: "",
  vaultId: "",
  autoSync: true,
};

export default class ObsidianSyncPlugin extends Plugin {
  settings: SyncPluginSettings = DEFAULT_SETTINGS;
  client: SyncClient | null = null;
  engine: SyncEngine | null = null;
  statusBar: SyncStatusBar | null = null;

  async onload(): Promise<void> {
    await this.loadSettings();

    this.addSettingTab(new SyncSettingTab(this.app, this));
    this.statusBar = new SyncStatusBar(this);

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
    };

    this.client = new SyncClient(config);

    if (!this.settings.vaultId) return;

    this.engine = new SyncEngine({
      vaultId: this.settings.vaultId,
      client: this.client,
      vault: this.app.vault,
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

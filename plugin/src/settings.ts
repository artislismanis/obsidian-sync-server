import { App, PluginSettingTab } from "obsidian";
import type ObsidianSyncPlugin from "./main";

export class SyncSettingTab extends PluginSettingTab {
  plugin: ObsidianSyncPlugin;

  constructor(app: App, plugin: ObsidianSyncPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Obsidian Sync Settings" });
    // Settings will be added in Phase 3
  }
}

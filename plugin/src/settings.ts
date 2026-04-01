import { App, Notice, PluginSettingTab, Setting } from "obsidian";
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

    new Setting(containerEl)
      .setName("Server URL")
      .setDesc("URL of your sync server (e.g., https://sync.example.com)")
      .addText((text) =>
        text
          .setPlaceholder("https://sync.example.com")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Vault ID")
      .setDesc("The vault ID on the server to sync with")
      .addText((text) =>
        text
          .setPlaceholder("vault-uuid")
          .setValue(this.plugin.settings.vaultId)
          .onChange(async (value) => {
            this.plugin.settings.vaultId = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Auto-sync")
      .setDesc("Automatically sync on file changes")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.autoSync)
          .onChange(async (value) => {
            this.plugin.settings.autoSync = value;
            await this.plugin.saveSettings();
          })
      );

    // Login section
    containerEl.createEl("h3", { text: "Authentication" });

    let usernameInput = "";
    let passwordInput = "";

    new Setting(containerEl).setName("Username").addText((text) =>
      text.setPlaceholder("username").onChange((value) => {
        usernameInput = value;
      })
    );

    new Setting(containerEl).setName("Password").addText((text) =>
      text
        .setPlaceholder("password")
        .then((t) => {
          t.inputEl.type = "password";
        })
        .onChange((value) => {
          passwordInput = value;
        })
    );

    new Setting(containerEl).addButton((btn) =>
      btn
        .setButtonText("Login")
        .setCta()
        .onClick(async () => {
          if (!this.plugin.settings.serverUrl) {
            new Notice("Set server URL first");
            return;
          }
          try {
            const { SyncClient } = await import("./sync/client");
            const client = new SyncClient({
              serverUrl: this.plugin.settings.serverUrl,
              accessToken: "",
              refreshToken: "",
            });
            const tokens = await client.login(usernameInput, passwordInput);
            this.plugin.settings.accessToken = tokens.access_token;
            this.plugin.settings.refreshToken = tokens.refresh_token;
            await this.plugin.saveSettings();
            new Notice("Login successful!");

            // Start sync if vault ID is set
            if (this.plugin.settings.vaultId) {
              await this.plugin.startSync();
            }
          } catch (e) {
            new Notice(`Login failed: ${e}`);
          }
        })
    );

    // Connection status
    if (this.plugin.settings.accessToken) {
      containerEl.createEl("p", {
        text: "Status: Authenticated",
        cls: "setting-item-description",
      });
    }
  }
}

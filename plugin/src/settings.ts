import { App, Notice, PluginSettingTab, Setting } from "obsidian";
import type ObsidianSyncPlugin from "./main";
import { SyncClient, type VaultInfo } from "./sync/client";

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

    // --- Server Connection ---
    new Setting(containerEl)
      .setName("Server URL")
      .setDesc("URL of your sync server")
      .addText((text) =>
        text
          .setPlaceholder("http://your-server:8000")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    // --- Authentication ---
    if (!this.plugin.settings.accessToken) {
      this.renderLoginSection(containerEl);
    } else {
      this.renderAuthenticatedSection(containerEl);
    }
  }

  private renderLoginSection(containerEl: HTMLElement): void {
    containerEl.createEl("h3", { text: "Login" });

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
            this.display();
          } catch (e) {
            new Notice(`Login failed: ${e}`);
          }
        })
    );
  }

  private renderAuthenticatedSection(containerEl: HTMLElement): void {
    new Setting(containerEl)
      .setName("Authenticated")
      .setDesc("Connected to server")
      .addButton((btn) =>
        btn.setButtonText("Logout").onClick(async () => {
          this.plugin.settings.accessToken = "";
          this.plugin.settings.refreshToken = "";
          this.plugin.settings.vaultId = "";
          this.plugin.stopSync();
          await this.plugin.saveSettings();
          this.display();
        })
      );

    // --- Vault Selection ---
    containerEl.createEl("h3", { text: "Vault" });

    if (this.plugin.settings.vaultId) {
      const vaultLabel = this.plugin.settings.vaultName
        ? `${this.plugin.settings.vaultName}`
        : this.plugin.settings.vaultId;
      new Setting(containerEl)
        .setName(vaultLabel)
        .setDesc(this.plugin.settings.vaultId)
        .addButton((btn) =>
          btn.setButtonText("Disconnect").onClick(async () => {
            this.plugin.settings.vaultId = "";
            this.plugin.settings.vaultName = "";
            this.plugin.stopSync();
            await this.plugin.saveSettings();
            this.display();
          })
        );
    } else {
      const vaultListEl = containerEl.createDiv({ cls: "vault-list-container" });
      vaultListEl.createEl("p", { text: "Loading vaults...", cls: "setting-item-description" });
      this.loadVaultList(vaultListEl);
    }

    // --- Device ---
    containerEl.createEl("h3", { text: "Device" });

    new Setting(containerEl)
      .setName("Device name")
      .setDesc("Identifies this device in sync logs and connected devices list")
      .addText((text) =>
        text
          .setValue(this.plugin.settings.deviceName)
          .onChange(async (value) => {
            this.plugin.settings.deviceName = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Device ID")
      .setDesc(this.plugin.settings.deviceId)
      .setDisabled(true);

    // --- Sync Settings ---
    containerEl.createEl("h3", { text: "Sync" });

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

    new Setting(containerEl)
      .setName("Conflict strategy")
      .setDesc("How to handle files that differ between local and server")
      .addDropdown((drop) =>
        drop
          .addOption("keep-both", "Keep both (conflict copy)")
          .addOption("server-wins", "Server wins")
          .addOption("local-wins", "Local wins")
          .setValue(this.plugin.settings.conflictStrategy || "keep-both")
          .onChange(async (value) => {
            this.plugin.settings.conflictStrategy = value;
            await this.plugin.saveSettings();
          })
      );
  }

  private async loadVaultList(container: HTMLElement): Promise<void> {
    try {
      const client = new SyncClient({
        serverUrl: this.plugin.settings.serverUrl,
        accessToken: this.plugin.settings.accessToken,
        refreshToken: this.plugin.settings.refreshToken,
      });

      const data = await client.listVaults();
      container.empty();

      if (data.length > 0) {
        container.createEl("p", {
          text: "Select a vault to sync with, or create a new one:",
          cls: "setting-item-description",
        });

        for (const vault of data) {
          new Setting(container)
            .setName(vault.name)
            .setDesc(`${vault.storage_backend} · ${vault.encrypted ? "encrypted" : "unencrypted"} · ${vault.sync_mode}`)
            .addButton((btn) =>
              btn
                .setButtonText("Connect")
                .setCta()
                .onClick(async () => {
                  await this.connectToVault(vault.id, vault.name);
                })
            );
        }
      } else {
        container.createEl("p", {
          text: "No vaults on the server yet. Create one:",
          cls: "setting-item-description",
        });
      }

      // Create new vault
      let newVaultName = "";
      new Setting(container)
        .setName("Create new vault")
        .addText((text) =>
          text.setPlaceholder("Vault name").onChange((value) => {
            newVaultName = value;
          })
        )
        .addButton((btn) =>
          btn.setButtonText("Create").onClick(async () => {
            if (!newVaultName.trim()) {
              new Notice("Enter a vault name");
              return;
            }
            try {
              const resp = await client.createVault(newVaultName.trim());
              new Notice(`Vault "${newVaultName}" created!`);
              await this.connectToVault(resp.id, newVaultName.trim());
            } catch (e) {
              new Notice(`Failed to create vault: ${e}`);
            }
          })
        );
    } catch (e) {
      container.empty();
      container.createEl("p", {
        text: `Failed to load vaults: ${e}`,
        cls: "setting-item-description",
      });
    }
  }

  private async connectToVault(vaultId: string, vaultName?: string): Promise<void> {
    this.plugin.settings.vaultId = vaultId;
    this.plugin.settings.vaultName = vaultName || "";
    await this.plugin.saveSettings();
    await this.plugin.startSync();
    this.display();
  }
}

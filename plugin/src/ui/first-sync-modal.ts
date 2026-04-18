import { App, Modal, Setting } from "obsidian";

export type ConflictStrategy = "server-wins" | "local-wins" | "keep-both";

export interface FirstSyncResult {
  confirmed: boolean;
  strategy: ConflictStrategy;
}

export class FirstSyncModal extends Modal {
  private result: FirstSyncResult = { confirmed: false, strategy: "keep-both" };
  private resolve: ((value: FirstSyncResult) => void) | null = null;
  private localFileCount: number;
  private serverFileCount: number;

  constructor(app: App, localFileCount: number, serverFileCount: number) {
    super(app);
    this.localFileCount = localFileCount;
    this.serverFileCount = serverFileCount;
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl("h2", { text: "Initial Sync" });

    const desc = contentEl.createDiv({ cls: "first-sync-desc" });
    desc.style.marginBottom = "16px";
    desc.style.lineHeight = "1.6";

    if (this.serverFileCount > 0 && this.localFileCount > 0) {
      desc.createEl("p", {
        text: `This vault has ${this.localFileCount} local files and ${this.serverFileCount} files on the server. Files will be merged.`,
      });
      desc.createEl("p", {
        text: "When the same file exists in both places with different content, choose how to handle conflicts:",
      });
    } else if (this.serverFileCount > 0) {
      desc.createEl("p", {
        text: `The server has ${this.serverFileCount} files. They will be downloaded to this vault.`,
      });
    } else {
      desc.createEl("p", {
        text: `This vault has ${this.localFileCount} files. They will be uploaded to the server.`,
      });
    }

    new Setting(contentEl)
      .setName("Conflict resolution")
      .setDesc("How to handle files that differ between local and server")
      .addDropdown((drop) =>
        drop
          .addOption("keep-both", "Keep both (save conflict copy)")
          .addOption("server-wins", "Server wins (overwrite local)")
          .addOption("local-wins", "Local wins (overwrite server)")
          .setValue(this.result.strategy)
          .onChange((value) => {
            this.result.strategy = value as ConflictStrategy;
          })
      );

    const strategies = contentEl.createDiv();
    strategies.style.fontSize = "12px";
    strategies.style.color = "var(--text-muted)";
    strategies.style.marginBottom = "16px";
    strategies.innerHTML = [
      "<b>Keep both</b> — conflicting files get a .conflict-timestamp copy. No data lost.",
      "<b>Server wins</b> — server version replaces local. Local changes discarded.",
      "<b>Local wins</b> — local version pushed to server. Server version overwritten.",
    ].join("<br>");

    const buttons = contentEl.createDiv({ cls: "first-sync-buttons" });
    buttons.style.display = "flex";
    buttons.style.justifyContent = "flex-end";
    buttons.style.gap = "8px";
    buttons.style.marginTop = "16px";

    const cancelBtn = buttons.createEl("button", { text: "Cancel" });
    cancelBtn.addEventListener("click", () => {
      this.result.confirmed = false;
      this.close();
    });

    const syncBtn = buttons.createEl("button", { text: "Start sync", cls: "mod-cta" });
    syncBtn.addEventListener("click", () => {
      this.result.confirmed = true;
      this.close();
    });
  }

  onClose(): void {
    if (this.resolve) {
      this.resolve(this.result);
      this.resolve = null;
    }
    this.contentEl.empty();
  }

  waitForResult(): Promise<FirstSyncResult> {
    return new Promise((resolve) => {
      this.resolve = resolve;
      this.open();
    });
  }
}

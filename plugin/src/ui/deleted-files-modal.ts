import { App, Modal, Notice } from "obsidian";
import { SyncClient } from "../sync/client";

interface DeletedFile {
  path: string;
  deleted_at: string;
  size_bytes: number;
  content_hash: string;
}

export class DeletedFilesModal extends Modal {
  private client: SyncClient;
  private vaultId: string;

  constructor(app: App, client: SyncClient, vaultId: string) {
    super(app);
    this.client = client;
    this.vaultId = vaultId;
  }

  async onOpen(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Deleted Files" });

    const loading = contentEl.createEl("p", { text: "Loading..." });

    try {
      const data = await this.client.getDeletedFiles(this.vaultId);
      loading.remove();
      const files = (data.files || []) as DeletedFile[];

      if (files.length === 0) {
        contentEl.createEl("p", { text: "No deleted files found." });
        return;
      }

      // Bulk restore button
      const header = contentEl.createDiv();
      header.style.display = "flex";
      header.style.justifyContent = "space-between";
      header.style.alignItems = "center";
      header.style.marginBottom = "12px";
      header.createEl("span", { text: `${files.length} deleted file${files.length > 1 ? "s" : ""}` });
      const bulkBtn = header.createEl("button", { text: "Restore all" });
      bulkBtn.addEventListener("click", async () => {
        for (const f of files) {
          try {
            await this.client.restoreDeletedFile(this.vaultId, f.path);
          } catch { /* continue */ }
        }
        new Notice(`Restored ${files.length} files`);
        this.close();
      });

      const table = contentEl.createDiv();
      table.style.maxHeight = "400px";
      table.style.overflowY = "auto";

      for (const file of files) {
        const row = table.createDiv();
        row.style.display = "flex";
        row.style.justifyContent = "space-between";
        row.style.alignItems = "center";
        row.style.padding = "6px 0";
        row.style.borderBottom = "1px solid var(--background-modifier-border)";

        const info = row.createDiv();
        info.createEl("div", { text: file.path }).style.fontFamily = "var(--font-monospace)";
        const meta = info.createEl("div");
        meta.style.fontSize = "11px";
        meta.style.color = "var(--text-muted)";
        const date = new Date(file.deleted_at).toLocaleString();
        const size = (file.size_bytes / 1024).toFixed(1);
        meta.setText(`Deleted ${date} · ${size} KB`);

        const restoreBtn = row.createEl("button", { text: "Restore" });
        restoreBtn.addEventListener("click", async () => {
          try {
            await this.client.restoreDeletedFile(this.vaultId, file.path);
            new Notice(`Restored: ${file.path}`);
            row.remove();
          } catch (e) {
            new Notice(`Failed to restore: ${e}`);
          }
        });
      }
    } catch (e) {
      loading.setText(`Failed to load deleted files: ${e}`);
    }
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

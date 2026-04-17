import { App, Modal } from "obsidian";

export class SyncLogModal extends Modal {
  private logs: string[];

  constructor(app: App, logs: string[]) {
    super(app);
    this.logs = logs;
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Sync Log" });

    if (this.logs.length === 0) {
      contentEl.createEl("p", {
        text: "No sync activity yet.",
        cls: "sync-log-empty",
      });
      return;
    }

    const container = contentEl.createDiv({ cls: "sync-log-container" });
    container.style.maxHeight = "400px";
    container.style.overflowY = "auto";
    container.style.fontFamily = "var(--font-monospace)";
    container.style.fontSize = "12px";
    container.style.lineHeight = "1.6";
    container.style.padding = "8px";
    container.style.backgroundColor = "var(--background-secondary)";
    container.style.borderRadius = "4px";

    // Show newest first
    for (let i = this.logs.length - 1; i >= 0; i--) {
      const line = container.createDiv();
      const entry = this.logs[i];

      if (entry.includes("↑")) {
        line.style.color = "var(--text-success)";
      } else if (entry.includes("↓")) {
        line.style.color = "var(--interactive-accent)";
      } else if (entry.includes("Failed") || entry.includes("conflict")) {
        line.style.color = "var(--text-error)";
      }

      line.setText(entry);
    }

    // Scroll to top (newest)
    container.scrollTop = 0;
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

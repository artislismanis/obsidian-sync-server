import { App, Modal, TFile, Vault, Notice, Setting } from "obsidian";
import { MergeModal } from "./merge-view";

export class ConflictResolverModal extends Modal {
  private vault: Vault;
  private conflicts: { original: TFile; conflict: TFile }[];
  private currentIndex = 0;

  constructor(app: App, vault: Vault) {
    super(app);
    this.vault = vault;
    this.conflicts = this.findConflicts();
  }

  private findConflicts(): { original: TFile; conflict: TFile }[] {
    const results: { original: TFile; conflict: TFile }[] = [];
    const allFiles = this.vault.getFiles();

    for (const file of allFiles) {
      const match = file.path.match(/^(.+)\.conflict-\d{4}-\d{2}-\d{2}T[\d-]+(\.\w+)$/);
      if (!match) continue;

      const originalPath = match[1] + match[2];
      const original = this.vault.getAbstractFileByPath(originalPath);
      if (original instanceof TFile) {
        results.push({ original, conflict: file });
      }
    }

    return results;
  }

  onOpen(): void {
    this.render();
  }

  private render(): void {
    const { contentEl } = this;
    contentEl.empty();

    if (this.conflicts.length === 0) {
      contentEl.createEl("h2", { text: "No Conflicts" });
      contentEl.createEl("p", { text: "All files are in sync. No conflict files found." });
      return;
    }

    const conflict = this.conflicts[this.currentIndex];
    contentEl.createEl("h2", {
      text: `Conflict ${this.currentIndex + 1} of ${this.conflicts.length}`,
    });

    contentEl.createEl("p", {
      text: conflict.original.path,
      cls: "conflict-file-path",
    });
    contentEl.querySelector(".conflict-file-path")!.setAttribute(
      "style",
      "font-family: var(--font-monospace); font-weight: 600; margin-bottom: 12px;"
    );

    const container = contentEl.createDiv();
    container.style.display = "grid";
    container.style.gridTemplateColumns = "1fr 1fr";
    container.style.gap = "12px";
    container.style.marginBottom = "16px";

    // Load both versions
    this.loadDiff(container, conflict);

    // Action buttons
    const actions = contentEl.createDiv();
    actions.style.display = "flex";
    actions.style.gap = "8px";
    actions.style.justifyContent = "center";
    actions.style.flexWrap = "wrap";

    const keepServerBtn = actions.createEl("button", { text: "Keep server version" });
    keepServerBtn.style.backgroundColor = "var(--interactive-accent)";
    keepServerBtn.style.color = "white";
    keepServerBtn.addEventListener("click", () =>
      this.resolve(conflict, "server")
    );

    const keepLocalBtn = actions.createEl("button", { text: "Keep local version" });
    keepLocalBtn.addEventListener("click", () =>
      this.resolve(conflict, "local")
    );

    const mergeBtn = actions.createEl("button", { text: "Merge versions", cls: "mod-cta" });
    mergeBtn.addEventListener("click", () =>
      this.openMerge(conflict)
    );

    const keepBothBtn = actions.createEl("button", { text: "Keep both" });
    keepBothBtn.addEventListener("click", () =>
      this.resolve(conflict, "both")
    );

    const skipBtn = actions.createEl("button", { text: "Skip" });
    skipBtn.addEventListener("click", () => {
      if (this.currentIndex < this.conflicts.length - 1) {
        this.currentIndex++;
        this.render();
      } else {
        this.close();
      }
    });
  }

  private async loadDiff(
    container: HTMLElement,
    conflict: { original: TFile; conflict: TFile }
  ): Promise<void> {
    let serverContent = "";
    let localContent = "";

    try {
      serverContent = await this.vault.read(conflict.original);
    } catch {
      serverContent = "(unable to read)";
    }
    try {
      localContent = await this.vault.read(conflict.conflict);
    } catch {
      localContent = "(unable to read)";
    }

    const leftCol = container.createDiv();
    leftCol.createEl("h4", { text: "Server version (current)" });
    const leftPre = leftCol.createEl("pre");
    leftPre.style.maxHeight = "300px";
    leftPre.style.overflow = "auto";
    leftPre.style.padding = "8px";
    leftPre.style.backgroundColor = "var(--background-secondary)";
    leftPre.style.borderRadius = "4px";
    leftPre.style.fontSize = "12px";
    leftPre.style.whiteSpace = "pre-wrap";
    leftPre.setText(serverContent);

    const rightCol = container.createDiv();
    rightCol.createEl("h4", { text: "Your version (conflict)" });
    const rightPre = rightCol.createEl("pre");
    rightPre.style.maxHeight = "300px";
    rightPre.style.overflow = "auto";
    rightPre.style.padding = "8px";
    rightPre.style.backgroundColor = "var(--background-secondary)";
    rightPre.style.borderRadius = "4px";
    rightPre.style.fontSize = "12px";
    rightPre.style.whiteSpace = "pre-wrap";
    rightPre.setText(localContent);
  }

  private async openMerge(conflict: { original: TFile; conflict: TFile }): Promise<void> {
    let serverContent = "";
    let localContent = "";
    try {
      serverContent = await this.vault.read(conflict.original);
      localContent = await this.vault.read(conflict.conflict);
    } catch {
      new Notice("Unable to read file contents for merge");
      return;
    }

    const modal = new MergeModal(this.app, serverContent, localContent);
    const result = await modal.waitForResult();

    if (result.merged) {
      await this.vault.modify(conflict.original, result.content);
      await this.vault.delete(conflict.conflict);
      new Notice(`Merged: ${conflict.original.path}`);
      this.conflicts.splice(this.currentIndex, 1);
      if (this.conflicts.length === 0) {
        new Notice("All conflicts resolved!");
        this.close();
      } else {
        if (this.currentIndex >= this.conflicts.length) this.currentIndex = 0;
        this.render();
      }
    }
  }

  private async resolve(
    conflict: { original: TFile; conflict: TFile },
    action: "server" | "local" | "both"
  ): Promise<void> {
    try {
      if (action === "local") {
        const localContent = await this.vault.readBinary(conflict.conflict);
        await this.vault.modifyBinary(conflict.original, localContent);
        await this.vault.delete(conflict.conflict);
        new Notice(`Kept your version of ${conflict.original.path}`);
      } else if (action === "server") {
        await this.vault.delete(conflict.conflict);
        new Notice(`Kept server version of ${conflict.original.path}`);
      } else {
        // both: rename conflict to a descriptive name and keep it
        const newName = conflict.original.path.replace(
          /(\.\w+)$/,
          `-local-copy$1`
        );
        await this.vault.rename(conflict.conflict, newName);
        new Notice(`Both versions kept for ${conflict.original.path}`);
      }
    } catch (e) {
      new Notice(`Error resolving conflict: ${e}`);
    }

    this.conflicts.splice(this.currentIndex, 1);
    if (this.conflicts.length === 0) {
      new Notice("All conflicts resolved!");
      this.close();
    } else {
      if (this.currentIndex >= this.conflicts.length) {
        this.currentIndex = 0;
      }
      this.render();
    }
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

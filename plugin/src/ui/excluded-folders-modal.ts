import { App, Modal, TFolder, Vault } from "obsidian";

export class ExcludedFoldersModal extends Modal {
  private vault: Vault;
  private excluded: Set<string>;
  private resolve: ((folders: string[]) => void) | null = null;

  constructor(app: App, vault: Vault, currentExcluded: string[]) {
    super(app);
    this.vault = vault;
    this.excluded = new Set(currentExcluded);
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Excluded Folders" });
    contentEl.createEl("p", {
      text: "Checked folders will NOT be synced.",
      cls: "setting-item-description",
    });

    const list = contentEl.createDiv({ cls: "excluded-folders-list" });
    list.style.maxHeight = "400px";
    list.style.overflowY = "auto";

    const root = this.vault.getRoot();
    for (const child of root.children) {
      if (!(child instanceof TFolder)) continue;
      if (child.name.startsWith(".")) continue;

      const row = list.createDiv();
      row.style.display = "flex";
      row.style.alignItems = "center";
      row.style.gap = "8px";
      row.style.padding = "4px 0";

      const cb = row.createEl("input", { type: "checkbox" }) as HTMLInputElement;
      cb.checked = this.excluded.has(child.path);
      cb.addEventListener("change", () => {
        if (cb.checked) {
          this.excluded.add(child.path);
        } else {
          this.excluded.delete(child.path);
        }
      });

      row.createEl("span", { text: child.path });
    }

    const buttons = contentEl.createDiv();
    buttons.style.display = "flex";
    buttons.style.justifyContent = "flex-end";
    buttons.style.gap = "8px";
    buttons.style.marginTop = "16px";

    const cancelBtn = buttons.createEl("button", { text: "Cancel" });
    cancelBtn.addEventListener("click", () => this.close());

    const saveBtn = buttons.createEl("button", { text: "Save", cls: "mod-cta" });
    saveBtn.addEventListener("click", () => {
      if (this.resolve) this.resolve(Array.from(this.excluded));
      this.close();
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }

  waitForResult(): Promise<string[]> {
    return new Promise((resolve) => {
      this.resolve = resolve;
      this.open();
    });
  }
}

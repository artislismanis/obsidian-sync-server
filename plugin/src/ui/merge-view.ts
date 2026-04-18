import { App, Modal, Notice } from "obsidian";
import { diffLines, type Change } from "diff";

export interface MergeResult {
  merged: boolean;
  content: string;
}

export class MergeModal extends Modal {
  private serverContent: string;
  private localContent: string;
  private hunks: Change[];
  private choices: ("left" | "right")[];
  private textarea: HTMLTextAreaElement | null = null;
  private resolve: ((result: MergeResult) => void) | null = null;

  constructor(app: App, serverContent: string, localContent: string) {
    super(app);
    this.serverContent = serverContent;
    this.localContent = localContent;
    this.hunks = diffLines(serverContent, localContent);
    this.choices = this.hunks.map((h) => (h.added ? "right" : "left"));
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("merge-modal");
    contentEl.style.width = "90vw";
    contentEl.style.maxWidth = "900px";

    contentEl.createEl("h2", { text: "Merge Versions" });
    contentEl.createEl("p", {
      text: "Click on a change to toggle between server (left) and your (right) version. Edit the merged result below.",
      cls: "setting-item-description",
    });

    this.renderDiff(contentEl);
    this.renderMergedResult(contentEl);
    this.renderButtons(contentEl);
    this.updateMergedResult();
  }

  private renderDiff(container: HTMLElement): void {
    const diffContainer = container.createDiv({ cls: "merge-diff" });
    diffContainer.style.display = "grid";
    diffContainer.style.gridTemplateColumns = "1fr auto 1fr";
    diffContainer.style.gap = "0";
    diffContainer.style.marginBottom = "16px";
    diffContainer.style.maxHeight = "300px";
    diffContainer.style.overflowY = "auto";
    diffContainer.style.border = "1px solid var(--background-modifier-border)";
    diffContainer.style.borderRadius = "4px";

    // Headers
    const lh = diffContainer.createDiv();
    lh.style.padding = "6px 8px";
    lh.style.fontWeight = "600";
    lh.style.backgroundColor = "var(--background-secondary)";
    lh.style.borderBottom = "1px solid var(--background-modifier-border)";
    lh.setText("Server version");

    const gh = diffContainer.createDiv();
    gh.style.backgroundColor = "var(--background-secondary)";
    gh.style.borderBottom = "1px solid var(--background-modifier-border)";

    const rh = diffContainer.createDiv();
    rh.style.padding = "6px 8px";
    rh.style.fontWeight = "600";
    rh.style.backgroundColor = "var(--background-secondary)";
    rh.style.borderBottom = "1px solid var(--background-modifier-border)";
    rh.setText("Your version");

    this.hunks.forEach((hunk, i) => {
      const leftCell = diffContainer.createDiv();
      const gutterCell = diffContainer.createDiv();
      const rightCell = diffContainer.createDiv();

      const cellStyle = "padding: 2px 8px; font-family: var(--font-monospace); font-size: 12px; white-space: pre-wrap; line-height: 1.5;";
      leftCell.setAttribute("style", cellStyle);
      rightCell.setAttribute("style", cellStyle);
      gutterCell.style.display = "flex";
      gutterCell.style.alignItems = "center";
      gutterCell.style.padding = "0 4px";

      if (!hunk.added && !hunk.removed) {
        leftCell.setText(hunk.value);
        rightCell.setText(hunk.value);
      } else if (hunk.removed) {
        leftCell.setText(hunk.value);
        leftCell.style.backgroundColor = "rgba(255, 80, 80, 0.15)";
        leftCell.style.cursor = "pointer";

        // Check if next hunk is the corresponding addition
        const next = this.hunks[i + 1];
        if (next && next.added) {
          rightCell.setText(next.value);
          rightCell.style.backgroundColor = "rgba(80, 200, 80, 0.15)";
          rightCell.style.cursor = "pointer";

          const btn = gutterCell.createEl("button", { text: this.choices[i] === "left" ? "◀" : "▶" });
          btn.style.fontSize = "14px";
          btn.style.padding = "2px 6px";
          btn.style.cursor = "pointer";
          btn.style.border = "1px solid var(--background-modifier-border)";
          btn.style.borderRadius = "3px";
          btn.style.backgroundColor = "var(--background-secondary)";

          const toggleChoice = () => {
            if (this.choices[i] === "left") {
              this.choices[i] = "right";
              this.choices[i + 1] = "right";
              btn.setText("▶");
              leftCell.style.opacity = "0.4";
              rightCell.style.opacity = "1";
            } else {
              this.choices[i] = "left";
              this.choices[i + 1] = "left";
              btn.setText("◀");
              leftCell.style.opacity = "1";
              rightCell.style.opacity = "0.4";
            }
            this.updateMergedResult();
          };

          btn.addEventListener("click", toggleChoice);
          leftCell.addEventListener("click", () => {
            if (this.choices[i] !== "left") toggleChoice();
          });
          rightCell.addEventListener("click", () => {
            if (this.choices[i] !== "right") toggleChoice();
          });

          // Initial state
          if (this.choices[i] === "right") {
            leftCell.style.opacity = "0.4";
          } else {
            rightCell.style.opacity = "0.4";
          }
        } else {
          leftCell.style.backgroundColor = "rgba(255, 80, 80, 0.15)";
          const btn = gutterCell.createEl("button", { text: this.choices[i] === "left" ? "◀" : "✗" });
          btn.style.fontSize = "12px";
          btn.style.padding = "2px 6px";
          btn.style.cursor = "pointer";
          btn.addEventListener("click", () => {
            this.choices[i] = this.choices[i] === "left" ? "right" : "left";
            btn.setText(this.choices[i] === "left" ? "◀" : "✗");
            leftCell.style.opacity = this.choices[i] === "left" ? "1" : "0.4";
            this.updateMergedResult();
          });
        }
      } else if (hunk.added) {
        // Skip if previous hunk was removed (already rendered as a pair)
        const prev = i > 0 ? this.hunks[i - 1] : null;
        if (prev && prev.removed) {
          leftCell.remove();
          gutterCell.remove();
          rightCell.remove();
          return;
        }
        rightCell.setText(hunk.value);
        rightCell.style.backgroundColor = "rgba(80, 200, 80, 0.15)";
        rightCell.style.cursor = "pointer";

        const btn = gutterCell.createEl("button", { text: this.choices[i] === "right" ? "▶" : "✗" });
        btn.style.fontSize = "12px";
        btn.style.padding = "2px 6px";
        btn.style.cursor = "pointer";
        btn.addEventListener("click", () => {
          this.choices[i] = this.choices[i] === "right" ? "left" : "right";
          btn.setText(this.choices[i] === "right" ? "▶" : "✗");
          rightCell.style.opacity = this.choices[i] === "right" ? "1" : "0.4";
          this.updateMergedResult();
        });
      }
    });
  }

  private renderMergedResult(container: HTMLElement): void {
    container.createEl("h3", { text: "Merged result" });
    const desc = container.createEl("p", { cls: "setting-item-description" });
    desc.setText("Edit freely or use the buttons above to pick changes.");

    this.textarea = container.createEl("textarea");
    this.textarea.style.width = "100%";
    this.textarea.style.height = "200px";
    this.textarea.style.fontFamily = "var(--font-monospace)";
    this.textarea.style.fontSize = "12px";
    this.textarea.style.padding = "8px";
    this.textarea.style.backgroundColor = "var(--background-secondary)";
    this.textarea.style.color = "var(--text-normal)";
    this.textarea.style.border = "1px solid var(--background-modifier-border)";
    this.textarea.style.borderRadius = "4px";
    this.textarea.style.resize = "vertical";
  }

  private renderButtons(container: HTMLElement): void {
    const buttons = container.createDiv();
    buttons.style.display = "flex";
    buttons.style.justifyContent = "flex-end";
    buttons.style.gap = "8px";
    buttons.style.marginTop = "12px";

    const cancelBtn = buttons.createEl("button", { text: "Cancel" });
    cancelBtn.addEventListener("click", () => {
      if (this.resolve) this.resolve({ merged: false, content: "" });
      this.close();
    });

    const saveBtn = buttons.createEl("button", { text: "Save merged version", cls: "mod-cta" });
    saveBtn.addEventListener("click", () => {
      if (this.resolve) this.resolve({ merged: true, content: this.textarea?.value || "" });
      this.close();
    });
  }

  private updateMergedResult(): void {
    if (!this.textarea) return;

    let result = "";
    for (let i = 0; i < this.hunks.length; i++) {
      const hunk = this.hunks[i];
      const choice = this.choices[i];

      if (!hunk.added && !hunk.removed) {
        result += hunk.value;
      } else if (hunk.removed) {
        const next = this.hunks[i + 1];
        if (next && next.added) {
          result += choice === "left" ? hunk.value : next.value;
          i++;
        } else {
          if (choice === "left") result += hunk.value;
        }
      } else if (hunk.added) {
        const prev = i > 0 ? this.hunks[i - 1] : null;
        if (prev && prev.removed) continue;
        if (choice === "right") result += hunk.value;
      }
    }

    this.textarea.value = result;
  }

  onClose(): void {
    if (this.resolve) {
      this.resolve({ merged: false, content: "" });
      this.resolve = null;
    }
    this.contentEl.empty();
  }

  waitForResult(): Promise<MergeResult> {
    return new Promise((resolve) => {
      this.resolve = resolve;
      this.open();
    });
  }
}

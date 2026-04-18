import { Menu, Notice, Plugin } from "obsidian";
import { SyncEngine } from "../sync/engine";
import { SyncClient } from "../sync/client";
import { SyncLogModal } from "./sync-log-modal";

export class SyncStatusBar {
  private el: HTMLElement;
  private plugin: Plugin;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private lastState = "";
  private engine: SyncEngine | null = null;
  private client: SyncClient | null = null;

  constructor(plugin: Plugin) {
    this.plugin = plugin;
    this.el = plugin.addStatusBarItem();
    this.el.addClass("obsidian-sync-status");
    this.el.setText("⏸ Sync");
    this.el.style.cursor = "pointer";

    this.el.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      this.showContextMenu(e);
    });

    this.el.addEventListener("click", () => {
      if (this.engine) {
        new SyncLogModal(this.plugin.app, this.engine.syncLog).open();
      }
    });
  }

  startMonitoring(engine: SyncEngine, client: SyncClient): void {
    this.stopMonitoring();
    this.engine = engine;
    this.client = client;
    this.intervalId = setInterval(() => this.update(), 2000);
    this.update();
  }

  stopMonitoring(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.engine = null;
    this.client = null;
    this.setState("⏸ Sync", "", "Sync: Idle");
  }

  destroy(): void {
    this.stopMonitoring();
    this.el.remove();
  }

  private setState(text: string, color: string, tooltip: string): void {
    const key = text + color;
    if (key === this.lastState) return;
    this.lastState = key;
    this.el.setText(text);
    this.el.style.color = color;
    this.el.setAttribute("aria-label", tooltip);
    this.el.setAttribute("data-tooltip-position", "top");
  }

  private update(): void {
    if (!this.engine || !this.client) return;

    const pending = this.engine.pendingChanges;
    const tracked = this.engine.trackedFileCount;
    const s = this.engine.stats;

    if (this.engine.isPaused) {
      this.setState(
        "⏸ Paused",
        "var(--text-muted)",
        `Sync: Paused\n${tracked} files tracked`
      );
    } else if (!this.client.isConnected) {
      this.setState(
        `⚡ ✗ ${pending > 0 ? pending : ""}`,
        "var(--text-error)",
        `Sync: Offline\n${pending} changes pending\n↑ ${s.uploaded}  ↓ ${s.downloaded}  ✗ ${s.deleted}\n${tracked} files tracked`
      );
    } else if (pending > 0) {
      this.setState(
        `⚡ ↑${pending}`,
        "var(--text-warning)",
        `Sync: Uploading ${pending} file${pending > 1 ? "s" : ""}...\n↑ ${s.uploaded}  ↓ ${s.downloaded}  ✗ ${s.deleted}\n${tracked} files tracked`
      );
    } else {
      this.setState(
        `⚡ ✓ ${tracked}`,
        "var(--text-success)",
        `Sync: Connected\n↑ ${s.uploaded}  ↓ ${s.downloaded}  ✗ ${s.deleted}\n${tracked} files on server`
      );
    }
  }

  private showContextMenu(e: MouseEvent): void {
    const menu = new Menu();

    if (this.engine?.isPaused) {
      menu.addItem((item) =>
        item
          .setTitle("Resume sync")
          .setIcon("play")
          .onClick(() => {
            this.engine?.resume();
          })
      );
    } else {
      menu.addItem((item) =>
        item
          .setTitle("Pause sync")
          .setIcon("pause")
          .onClick(() => {
            this.engine?.pause();
          })
      );

      menu.addItem((item) =>
        item
          .setTitle("Sync now")
          .setIcon("refresh-cw")
          .onClick(() => {
            this.plugin.app.commands.executeCommandById(
              "obsidian-sync:force-sync"
            );
          })
      );
    }

    menu.addItem((item) =>
      item
        .setTitle("View sync log")
        .setIcon("file-text")
        .onClick(() => {
          if (this.engine) {
            new SyncLogModal(this.plugin.app, this.engine.syncLog).open();
          }
        })
    );

    menu.addSeparator();

    if (this.engine) {
      const s = this.engine.stats;
      const tracked = this.engine.trackedFileCount;
      menu.addItem((item) =>
        item
          .setTitle(`↑ ${s.uploaded} uploaded  ↓ ${s.downloaded} downloaded`)
          .setDisabled(true)
      );
      menu.addItem((item) =>
        item.setTitle(`${tracked} files on server`).setDisabled(true)
      );
    }

    menu.addSeparator();

    menu.addItem((item) =>
      item
        .setTitle("Plugin settings")
        .setIcon("settings")
        .onClick(() => {
          (this.plugin.app as unknown as { setting: { open: () => void; openTabById: (id: string) => void } }).setting.open();
          (this.plugin.app as unknown as { setting: { openTabById: (id: string) => void } }).setting.openTabById("obsidian-sync");
        })
    );

    menu.showAtMouseEvent(e);
  }
}

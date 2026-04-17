import { Plugin } from "obsidian";
import { SyncEngine } from "../sync/engine";
import { SyncClient } from "../sync/client";

export class SyncStatusBar {
  private el: HTMLElement;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private lastText = "";

  constructor(plugin: Plugin) {
    this.el = plugin.addStatusBarItem();
    this.el.setText("Sync: Idle");
  }

  startMonitoring(engine: SyncEngine, client: SyncClient): void {
    this.stopMonitoring();
    this.intervalId = setInterval(() => {
      this.update(engine, client);
    }, 2000);
    this.update(engine, client);
  }

  stopMonitoring(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.setText("Sync: Idle", "");
  }

  destroy(): void {
    this.stopMonitoring();
    this.el.remove();
  }

  private setText(text: string, color: string): void {
    if (text === this.lastText) return;
    this.lastText = text;
    this.el.setText(text);
    this.el.style.color = color;
  }

  private update(engine: SyncEngine, client: SyncClient): void {
    const pending = engine.pendingChanges;
    const tracked = engine.trackedFileCount;
    if (!client.isConnected) {
      this.setText(
        `Sync: Offline (${pending} pending)`,
        "var(--text-error)"
      );
    } else if (pending > 0) {
      this.setText(
        `Sync: Uploading ${pending} file${pending > 1 ? "s" : ""}...`,
        "var(--text-warning)"
      );
    } else {
      this.setText(
        `Sync: ${tracked} file${tracked !== 1 ? "s" : ""} synced`,
        "var(--text-success)"
      );
    }
  }
}

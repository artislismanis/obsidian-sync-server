import { Plugin } from "obsidian";
import { SyncEngine } from "../sync/engine";
import { SyncClient } from "../sync/client";

export class SyncStatusBar {
  private el: HTMLElement;
  private intervalId: ReturnType<typeof setInterval> | null = null;

  constructor(plugin: Plugin) {
    this.el = plugin.addStatusBarItem();
    this.el.setText("Sync: Idle");
  }

  startMonitoring(engine: SyncEngine, client: SyncClient): void {
    this.stopMonitoring();
    this.intervalId = setInterval(() => {
      this.update(engine, client);
    }, 2000);
  }

  stopMonitoring(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.el.setText("Sync: Idle");
    this.el.style.color = "";
  }

  destroy(): void {
    this.stopMonitoring();
    this.el.remove();
  }

  private update(engine: SyncEngine, client: SyncClient): void {
    const pending = engine.pendingChanges;
    if (!client.isConnected) {
      this.el.setText(`Sync: Offline (${pending} pending)`);
      this.el.style.color = "var(--text-error)";
    } else if (pending > 0) {
      this.el.setText(`Sync: ${pending} pending`);
      this.el.style.color = "var(--text-warning)";
    } else {
      this.el.setText("Sync: Connected");
      this.el.style.color = "var(--text-success)";
    }
  }
}

import { Plugin } from "obsidian";
import { SyncSettingTab } from "./settings";

export default class ObsidianSyncPlugin extends Plugin {
  async onload(): Promise<void> {
    console.log("Obsidian Sync plugin loaded");
    this.addSettingTab(new SyncSettingTab(this.app, this));
  }

  async onunload(): Promise<void> {
    console.log("Obsidian Sync plugin unloaded");
  }
}

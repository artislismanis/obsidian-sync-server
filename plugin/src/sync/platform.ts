import { Platform } from "obsidian";

export interface SyncProfile {
  debounceMs: number;
  maxConcurrentUploads: number;
  liveSyncDefault: boolean;
  maxAutoSyncBytes: number;
  wsReconnectMaxDelayMs: number;
  wifiOnlyLargeFiles: boolean;
  batteryAwareThrottle: boolean;
}

const DESKTOP_PROFILE: SyncProfile = {
  debounceMs: 2000,
  maxConcurrentUploads: 10,
  liveSyncDefault: true,
  maxAutoSyncBytes: Infinity,
  wsReconnectMaxDelayMs: 10000,
  wifiOnlyLargeFiles: false,
  batteryAwareThrottle: false,
};

const MOBILE_PROFILE: SyncProfile = {
  debounceMs: 5000,
  maxConcurrentUploads: 3,
  liveSyncDefault: false,
  maxAutoSyncBytes: 20 * 1024 * 1024, // 20MB
  wsReconnectMaxDelayMs: 30000,
  wifiOnlyLargeFiles: true,
  batteryAwareThrottle: true,
};

export function getSyncProfile(): SyncProfile {
  if (Platform.isMobileApp) {
    return { ...MOBILE_PROFILE };
  }
  return { ...DESKTOP_PROFILE };
}

export function isMobile(): boolean {
  return Platform.isMobileApp;
}

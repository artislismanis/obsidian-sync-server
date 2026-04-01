/**
 * Offline change queue — stores pending sync operations
 * when the server is unreachable.
 */

export interface QueuedChange {
  type: "create" | "update" | "delete" | "rename";
  path: string;
  newPath?: string; // for renames
  timestamp: number;
}

export class SyncQueue {
  private queue: QueuedChange[] = [];

  enqueue(change: QueuedChange): void {
    // Deduplicate: if same path already queued, replace with latest
    const existing = this.queue.findIndex(
      (c) => c.path === change.path && c.type !== "rename"
    );
    if (existing >= 0 && change.type !== "rename") {
      // A delete supersedes previous creates/updates
      if (change.type === "delete") {
        this.queue.splice(existing, 1);
      } else {
        this.queue[existing] = change;
        return;
      }
    }
    this.queue.push(change);
  }

  dequeue(): QueuedChange | undefined {
    return this.queue.shift();
  }

  peek(): QueuedChange | undefined {
    return this.queue[0];
  }

  get length(): number {
    return this.queue.length;
  }

  clear(): void {
    this.queue = [];
  }

  getAll(): QueuedChange[] {
    return [...this.queue];
  }

  isEmpty(): boolean {
    return this.queue.length === 0;
  }
}

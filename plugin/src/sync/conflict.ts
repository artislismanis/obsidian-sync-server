/**
 * Conflict detection and resolution utilities.
 */

/**
 * Generate a conflict file path. E.g., "note.md" -> "note.conflict-2026-04-01T12-00-00.md"
 */
export function conflictPath(originalPath: string): string {
  const now = new Date();
  const timestamp = now.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const dotIndex = originalPath.lastIndexOf(".");
  if (dotIndex === -1) {
    return `${originalPath}.conflict-${timestamp}`;
  }
  const base = originalPath.slice(0, dotIndex);
  const ext = originalPath.slice(dotIndex);
  return `${base}.conflict-${timestamp}${ext}`;
}

export interface ConflictInfo {
  path: string;
  conflictPath: string;
  serverVersion: number;
  clientVersion: number;
}

import { useEffect, useState } from "react";
import { api, type FileVersionInfo } from "../api/client";

interface FileHistoryProps {
  vaultId: string;
  filePath: string;
  onBack: () => void;
}

export function FileHistory({ vaultId, filePath, onBack }: FileHistoryProps) {
  const [versions, setVersions] = useState<FileVersionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [restoring, setRestoring] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .getFileHistory(vaultId, filePath)
      .then((data) => {
        setVersions(data.versions);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load history");
        setLoading(false);
      });
  }, [vaultId, filePath]);

  async function handleRestore(version: number) {
    setRestoring(version);
    try {
      await api.restoreFileVersion(vaultId, filePath, version);
      // Refresh the version list after restoring
      const data = await api.getFileHistory(vaultId, filePath);
      setVersions(data.versions);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to restore version");
    } finally {
      setRestoring(null);
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  if (loading) return <div className="loading">Loading file history...</div>;

  return (
    <div className="file-history">
      <div className="browser-header">
        <button onClick={onBack}>&larr; Back</button>
        <h2>History: {filePath}</h2>
      </div>

      {error && <div className="error-message">{error}</div>}

      {versions.length === 0 ? (
        <p className="empty">No version history available.</p>
      ) : (
        <table className="history-table">
          <thead>
            <tr>
              <th>Version</th>
              <th>Author</th>
              <th>Date</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.version}>
                <td>{v.version}</td>
                <td>{v.author_id}</td>
                <td>{new Date(v.created_at).toLocaleString()}</td>
                <td>{formatSize(v.size_bytes)}</td>
                <td>
                  <button
                    className="restore-btn"
                    disabled={restoring !== null}
                    onClick={() => handleRestore(v.version)}
                  >
                    {restoring === v.version ? "Restoring..." : "Restore"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

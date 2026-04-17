import { useEffect, useState, type FormEvent } from "react";
import { api, type ShareData } from "../api/client";
import { MarkdownRenderer } from "../components/MarkdownRenderer";

interface ShareViewProps {
  token: string;
}

export function ShareView({ token }: ShareViewProps) {
  const [share, setShare] = useState<ShareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");

  useEffect(() => {
    fetchShare();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function fetchShare(pw?: string) {
    setLoading(true);
    setError("");
    try {
      const data = await api.getShareLink(token, pw);
      setShare(data);
      setNeedsPassword(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      if (message.toLowerCase().includes("password")) {
        setNeedsPassword(true);
        if (pw) {
          setPasswordError("Incorrect password. Please try again.");
        }
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setPasswordError("");
    fetchShare(password);
  }

  if (loading) return <div className="loading">Loading shared content...</div>;

  if (error) {
    return (
      <div className="share-view">
        <div className="share-error">
          <h2>Share Link Error</h2>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (needsPassword) {
    return (
      <div className="share-view">
        <div className="share-password">
          <h2>Password Required</h2>
          <p>This shared content is password-protected.</p>
          <form onSubmit={handlePasswordSubmit}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoFocus
            />
            <button type="submit">View Content</button>
          </form>
          {passwordError && <p className="error-message">{passwordError}</p>}
        </div>
      </div>
    );
  }

  if (!share) return null;

  const isMarkdown = share.file_path.endsWith(".md");

  return (
    <div className="share-view">
      <div className="share-header">
        <h2>{share.file_path}</h2>
        <span className="share-meta">
          Shared by {share.shared_by} on{" "}
          {new Date(share.created_at).toLocaleDateString()}
        </span>
      </div>
      <div className="share-content">
        {isMarkdown ? (
          <MarkdownRenderer content={share.content} />
        ) : (
          <pre>{share.content}</pre>
        )}
      </div>
    </div>
  );
}

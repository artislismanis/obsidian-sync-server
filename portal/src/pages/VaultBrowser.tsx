import { useEffect, useState } from "react";
import { api, type FileInfo } from "../api/client";
import { MarkdownRenderer } from "../components/MarkdownRenderer";

interface VaultBrowserProps {
  vaultId: string;
  onBack: () => void;
}

export function VaultBrowser({ vaultId, onBack }: VaultBrowserProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getVaultFiles(vaultId).then((data) => {
      setFiles(data.files);
      setLoading(false);
    });
  }, [vaultId]);

  async function openFile(path: string) {
    setSelectedFile(path);
    try {
      const data = await api.getFileContent(vaultId, path);
      // Decode base64 content
      const decoded = atob(data.content);
      setFileContent(decoded);
    } catch {
      setFileContent("Error loading file");
    }
  }

  // Build tree structure from flat file paths
  const tree = buildTree(files);

  if (loading) return <div className="loading">Loading files...</div>;

  return (
    <div className="vault-browser">
      <div className="browser-header">
        <button onClick={onBack}>&larr; Back</button>
        <h2>Vault Files</h2>
      </div>
      <div className="browser-layout">
        <div className="file-tree">
          <TreeNode node={tree} onSelectFile={openFile} selectedPath={selectedFile} />
        </div>
        <div className="file-content">
          {selectedFile ? (
            <>
              <h3>{selectedFile}</h3>
              {selectedFile.endsWith(".md") ? (
                <MarkdownRenderer content={fileContent} />
              ) : (
                <pre>{fileContent}</pre>
              )}
            </>
          ) : (
            <p className="empty">Select a file to view</p>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Tree building ---

interface TreeNodeData {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNodeData[];
  file?: FileInfo;
}

function buildTree(files: FileInfo[]): TreeNodeData {
  const root: TreeNodeData = { name: "/", path: "", isDir: true, children: [] };

  for (const file of files) {
    const parts = file.path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;

      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: parts.slice(0, i + 1).join("/"),
          isDir: !isLast,
          children: [],
          file: isLast ? file : undefined,
        };
        current.children.push(child);
      }
      current = child;
    }
  }

  // Sort: directories first, then alphabetical
  sortTree(root);
  return root;
}

function sortTree(node: TreeNodeData): void {
  node.children.sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  node.children.forEach(sortTree);
}

function TreeNode({
  node,
  onSelectFile,
  selectedPath,
  depth = 0,
}: {
  node: TreeNodeData;
  onSelectFile: (path: string) => void;
  selectedPath: string | null;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);

  return (
    <div style={{ paddingLeft: depth > 0 ? 16 : 0 }}>
      {node.isDir ? (
        <>
          {node.name !== "/" && (
            <div className="tree-dir" onClick={() => setExpanded(!expanded)}>
              {expanded ? "📂" : "📁"} {node.name}
            </div>
          )}
          {expanded &&
            node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                onSelectFile={onSelectFile}
                selectedPath={selectedPath}
                depth={depth + 1}
              />
            ))}
        </>
      ) : (
        <div
          className={`tree-file ${selectedPath === node.path ? "selected" : ""}`}
          onClick={() => onSelectFile(node.path)}
        >
          📄 {node.name}
        </div>
      )}
    </div>
  );
}

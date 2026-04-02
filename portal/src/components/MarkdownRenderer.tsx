interface MarkdownRendererProps {
  content: string;
}

/**
 * Simple markdown renderer. Converts basic markdown to HTML.
 * For production, use a library like react-markdown or marked.
 */
export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const html = simpleMarkdownToHtml(content);
  return (
    <div
      className="markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function simpleMarkdownToHtml(md: string): string {
  let html = escapeHtml(md);

  // Headers
  html = html.replace(/^######\s+(.+)$/gm, "<h6>$1</h6>");
  html = html.replace(/^#####\s+(.+)$/gm, "<h5>$1</h5>");
  html = html.replace(/^####\s+(.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");

  // Bold and italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Links — sanitize URLs to prevent javascript: XSS
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_match: string, text: string, url: string) => {
      const sanitized = sanitizeUrl(url);
      return `<a href="${sanitized}" target="_blank" rel="noopener noreferrer">${text}</a>`;
    }
  );

  // Lists
  html = html.replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

  // Horizontal rules
  html = html.replace(/^---+$/gm, "<hr>");

  // Paragraphs (lines not already in tags)
  html = html.replace(/^(?!<[huplo]|<li|<hr|<pre)(.+)$/gm, "<p>$1</p>");

  // Line breaks
  html = html.replace(/\n{2,}/g, "\n");

  return html;
}

const SAFE_URL_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function sanitizeUrl(url: string): string {
  try {
    // URL constructor normalizes the protocol
    const parsed = new URL(url, "https://placeholder");
    if (!SAFE_URL_PROTOCOLS.has(parsed.protocol)) {
      return "";
    }
  } catch {
    // Relative URLs are safe
    if (url.includes(":") && !url.startsWith("/") && !url.startsWith(".")) {
      return "";
    }
  }
  return url;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

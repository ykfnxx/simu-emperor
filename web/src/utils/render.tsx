import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function renderMarkdown(content: string, isPlayer: boolean) {
  // Player messages use hardcoded light-on-dark; agent messages use CSS vars
  const textStyle = isPlayer
    ? { color: 'var(--color-text-inverse)' }
    : { color: 'var(--color-text)' };
  const mutedStyle = isPlayer
    ? { color: 'var(--color-player-meta)' }
    : { color: 'var(--color-text-secondary)' };
  const linkStyle = isPlayer
    ? { color: 'var(--color-player-meta)', textDecoration: 'underline' as const }
    : { color: 'var(--color-primary)', textDecoration: 'underline' as const };
  const quoteStyle = isPlayer
    ? { borderColor: 'var(--color-player-meta)', color: 'var(--color-player-meta)' }
    : { borderColor: 'var(--color-quote-border)', color: 'var(--color-quote-text)' };
  const codeStyle = isPlayer
    ? { backgroundColor: 'rgba(59,130,246,0.4)', color: 'var(--color-text-inverse)' }
    : { backgroundColor: 'var(--color-code-bg)', color: 'var(--color-code-text)' };
  const preStyle = isPlayer
    ? { backgroundColor: 'rgba(30,64,175,0.7)', color: 'var(--color-player-meta)' }
    : { backgroundColor: 'var(--color-pre-bg)', color: 'var(--color-pre-text)' };

  return (
    <div className="mt-1 space-y-2 text-sm leading-6">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="whitespace-pre-wrap" style={textStyle}>{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5" style={textStyle}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5" style={textStyle}>{children}</ol>
          ),
          li: ({ children }) => <li style={textStyle}>{children}</li>,
          strong: ({ children }) => <strong style={textStyle}>{children}</strong>,
          em: ({ children }) => <em style={mutedStyle}>{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 pl-3 italic" style={quoteStyle}>{children}</blockquote>
          ),
          code: ({ children }) => (
            <code className="rounded px-1 py-0.5 text-xs" style={codeStyle}>{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded-lg p-3 text-xs" style={preStyle}>{children}</pre>
          ),
          a: ({ href, children }) => (
            <a href={href} style={linkStyle} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

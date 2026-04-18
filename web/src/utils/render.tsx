import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function renderMarkdown(content: string, isPlayer: boolean) {
  const textTone = isPlayer ? 'text-white' : 'text-slate-700';
  const mutedTone = isPlayer ? 'text-blue-100' : 'text-slate-500';
  const linkTone = isPlayer ? 'text-blue-100 underline' : 'text-blue-600 underline';
  const quoteTone = isPlayer ? 'border-blue-300 text-blue-100' : 'border-slate-300 text-slate-600';
  const codeTone = isPlayer ? 'bg-blue-500/60 text-white' : 'bg-slate-200 text-slate-800';
  const preTone = isPlayer ? 'bg-blue-700/70 text-blue-50' : 'bg-slate-900 text-slate-100';

  return (
    <div className="mt-1 space-y-2 text-sm leading-6">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className={`whitespace-pre-wrap ${textTone}`}>{children}</p>,
          ul: ({ children }) => (
            <ul className={`list-disc space-y-1 pl-5 ${textTone}`}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className={`list-decimal space-y-1 pl-5 ${textTone}`}>{children}</ol>
          ),
          li: ({ children }) => <li className={textTone}>{children}</li>,
          strong: ({ children }) => <strong className={textTone}>{children}</strong>,
          em: ({ children }) => <em className={mutedTone}>{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className={`border-l-2 pl-3 italic ${quoteTone}`}>{children}</blockquote>
          ),
          code: ({ children }) => (
            <code className={`rounded px-1 py-0.5 text-xs ${codeTone}`}>{children}</code>
          ),
          pre: ({ children }) => (
            <pre className={`overflow-x-auto rounded-lg p-3 text-xs ${preTone}`}>{children}</pre>
          ),
          a: ({ href, children }) => (
            <a href={href} className={linkTone} target="_blank" rel="noreferrer">
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

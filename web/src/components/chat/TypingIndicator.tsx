interface TypingIndicatorProps {
  agentName: string;
}

export function TypingIndicator({ agentName }: TypingIndicatorProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[55%] rounded-2xl px-4 py-3" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)', color: 'var(--color-text)' }}>
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{agentName} · 输入中...</p>
        <div className="mt-2 flex items-center gap-1.5">
          <span className="h-2 w-2 animate-pulse rounded-full" style={{ backgroundColor: 'var(--color-text-muted)' }} />
          <span
            className="h-2 w-2 animate-pulse rounded-full"
            style={{ backgroundColor: 'var(--color-text-muted)', animationDelay: '120ms' }}
          />
          <span
            className="h-2 w-2 animate-pulse rounded-full"
            style={{ backgroundColor: 'var(--color-text-muted)', animationDelay: '240ms' }}
          />
        </div>
      </div>
    </div>
  );
}

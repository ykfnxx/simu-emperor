interface TypingIndicatorProps {
  agentName: string;
}

export function TypingIndicator({ agentName }: TypingIndicatorProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[55%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-700">
        <p className="text-xs text-slate-500">{agentName} · 输入中...</p>
        <div className="mt-2 flex items-center gap-1.5">
          <span className="h-2 w-2 animate-pulse rounded-full bg-slate-400" />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-slate-400"
            style={{ animationDelay: '120ms' }}
          />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-slate-400"
            style={{ animationDelay: '240ms' }}
          />
        </div>
      </div>
    </div>
  );
}

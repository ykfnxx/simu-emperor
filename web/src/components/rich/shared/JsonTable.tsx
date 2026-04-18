interface JsonTableProps {
  data: Record<string, unknown>;
  className?: string;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') {
    return new Intl.NumberFormat('zh-CN').format(value);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function JsonTable({ data, className = '' }: JsonTableProps) {
  const entries = Object.entries(data).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  );
  if (entries.length === 0) return null;

  return (
    <table className={`w-full text-xs ${className}`}>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key} className="border-b border-slate-100 last:border-0">
            <td className="py-1 pr-3 font-medium text-slate-500">{key}</td>
            <td className="py-1 text-slate-700">{formatValue(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

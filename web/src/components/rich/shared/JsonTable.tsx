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
          <tr key={key} style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }} className="last:border-0">
            <td className="py-1 pr-3 font-medium" style={{ color: 'var(--color-text-secondary)' }}>{key}</td>
            <td className="py-1" style={{ color: 'var(--color-text)' }}>{formatValue(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

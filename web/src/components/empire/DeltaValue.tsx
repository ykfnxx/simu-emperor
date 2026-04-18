import { formatNumber } from '../../utils/format';

interface DeltaValueProps {
  value: number;
  delta?: number;
  format?: boolean;
}

export function DeltaValue({ value, delta, format = true }: DeltaValueProps) {
  const deltaNum = delta ?? 0;
  const displayValue = format ? formatNumber(Math.round(value)) : String(value);

  if (delta === undefined) {
    return <span>{displayValue}</span>;
  }

  if (Math.abs(deltaNum) < 0.01) {
    return <span>{displayValue} (0)</span>;
  }

  if (deltaNum > 0) {
    const formattedDelta = format ? formatNumber(Math.round(deltaNum)) : String(deltaNum);
    return (
      <span>
        {displayValue} <span className="text-green-600">(+{formattedDelta})</span>
      </span>
    );
  }

  const formattedDelta = format
    ? formatNumber(Math.round(Math.abs(deltaNum)))
    : String(Math.abs(deltaNum));
  return (
    <span>
      {displayValue} <span className="text-red-600">(-{formattedDelta})</span>
    </span>
  );
}

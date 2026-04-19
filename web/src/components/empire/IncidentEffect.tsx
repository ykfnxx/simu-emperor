interface IncidentEffectProps {
  value: number;
  incidentEffect?: number;
}

export function IncidentEffect({ value, incidentEffect }: IncidentEffectProps) {
  const effectNum = incidentEffect ?? 0;
  if (Math.abs(effectNum) < 0.0001) {
    return <span>{value.toFixed(2)}%</span>;
  }

  const effectValue = effectNum * 100;
  const absEffect = Math.abs(effectValue);

  if (effectValue > 0) {
    return (
      <span>
        {value.toFixed(2)}% <span style={{ color: 'var(--color-delta-positive)' }}>+{absEffect.toFixed(2)}%</span>
      </span>
    );
  }

  return (
    <span>
      {value.toFixed(2)}% <span style={{ color: 'var(--color-delta-negative)' }}>-{absEffect.toFixed(2)}%</span>
    </span>
  );
}

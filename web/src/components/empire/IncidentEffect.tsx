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
        {value.toFixed(2)}% <span className="text-green-600">+{absEffect.toFixed(2)}%</span>
      </span>
    );
  }

  return (
    <span>
      {value.toFixed(2)}% <span className="text-red-600">-{absEffect.toFixed(2)}%</span>
    </span>
  );
}

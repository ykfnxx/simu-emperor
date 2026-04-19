import type { Incident } from '../../api/types';

interface IncidentDetailDialogProps {
  incident: Incident;
  onClose: () => void;
}

export function IncidentDetailDialog({ incident, onClose }: IncidentDetailDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-overlay)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl p-6 shadow-xl"
        style={{ backgroundColor: 'var(--color-surface)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>{incident.title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 hover:opacity-80"
            style={{ color: 'var(--color-text-muted)' }}
          >
            ✕
          </button>
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <span style={{ color: 'var(--color-text-secondary)' }}>来源：</span>
            <span style={{ color: 'var(--color-text)' }}>{incident.source}</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-secondary)' }}>剩余时间：</span>
            <span style={{ color: 'var(--color-text)' }}>{incident.remaining_ticks} 周</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-secondary)' }}>描述：</span>
            <p className="mt-1" style={{ color: 'var(--color-text)' }}>{incident.description}</p>
          </div>
          {incident.effects.length > 0 && (
            <div>
              <span style={{ color: 'var(--color-text-secondary)' }}>影响：</span>
              <div className="mt-2 space-y-1">
                {incident.effects.map((effect, idx) => (
                  <div key={idx} className="rounded p-2 text-xs" style={{ backgroundColor: 'var(--color-surface-alt)' }}>
                    <div className="font-mono" style={{ color: 'var(--color-text)' }}>{effect.target_path}</div>
                    {effect.add && <div style={{ color: 'var(--color-info-text)' }}>+{effect.add}</div>}
                    {effect.factor && <div style={{ color: 'var(--color-delta-positive)' }}>×{effect.factor}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

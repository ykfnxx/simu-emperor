import type { Incident } from '../../api/types';

interface IncidentDetailDialogProps {
  incident: Incident;
  onClose: () => void;
}

export function IncidentDetailDialog({ incident, onClose }: IncidentDetailDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">{incident.title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <span className="text-slate-500">来源：</span>
            <span className="text-slate-900">{incident.source}</span>
          </div>
          <div>
            <span className="text-slate-500">剩余时间：</span>
            <span className="text-slate-900">{incident.remaining_ticks} 周</span>
          </div>
          <div>
            <span className="text-slate-500">描述：</span>
            <p className="mt-1 text-slate-900">{incident.description}</p>
          </div>
          {incident.effects.length > 0 && (
            <div>
              <span className="text-slate-500">影响：</span>
              <div className="mt-2 space-y-1">
                {incident.effects.map((effect, idx) => (
                  <div key={idx} className="rounded bg-slate-50 p-2 text-xs">
                    <div className="font-mono text-slate-700">{effect.target_path}</div>
                    {effect.add && <div className="text-blue-600">+{effect.add}</div>}
                    {effect.factor && <div className="text-green-600">×{effect.factor}</div>}
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

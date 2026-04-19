import { ClipboardList } from 'lucide-react';

import { useEmpireStore } from '../../stores/empireStore';

export function IncidentPanel() {
  const { incidents, setSelectedIncident } = useEmpireStore();

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      {incidents.length === 0 ? (
        <div className="rounded-xl p-6 text-center" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)', color: 'var(--color-text-secondary)' }}>
          <p>当前无大事发生</p>
        </div>
      ) : (
        incidents.map((incident) => (
          <div
            key={incident.incident_id}
            onClick={() => setSelectedIncident(incident)}
            className="cursor-pointer rounded-xl p-3 transition-colors hover:opacity-90"
            style={{ borderWidth: 1, borderColor: 'var(--color-danger-border)', borderStyle: 'solid', backgroundColor: 'var(--color-danger-soft)' }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ClipboardList className="h-4 w-4" style={{ color: 'var(--color-danger)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{incident.title}</span>
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span>{incident.remaining_ticks} 周</span>
                <span>→</span>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

import { ClipboardList } from 'lucide-react';

import { useEmpireStore } from '../../stores/empireStore';

export function IncidentPanel() {
  const { incidents, setSelectedIncident } = useEmpireStore();

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      {incidents.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-slate-500">
          <p>当前无大事发生</p>
        </div>
      ) : (
        incidents.map((incident) => (
          <div
            key={incident.incident_id}
            onClick={() => setSelectedIncident(incident)}
            className="cursor-pointer rounded-xl border border-red-100 bg-red-50 p-3 transition-colors hover:border-red-200 hover:bg-red-100"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ClipboardList className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-900">{incident.title}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
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

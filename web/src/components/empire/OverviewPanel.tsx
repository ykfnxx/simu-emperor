import { Coins, MapPin, Users } from 'lucide-react';

import { useEmpireStore } from '../../stores/empireStore';
import { DeltaValue } from './DeltaValue';

export function OverviewPanel() {
  const overview = useEmpireStore((s) => s.overview);

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-warning-border)', borderStyle: 'solid', backgroundColor: 'var(--color-warning-soft)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-warning-text)' }}>
          <Coins className="h-4 w-4" />
          <span>国库资金</span>
        </div>
        <p className="mt-2 text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={overview.treasury} delta={overview.treasury_delta} format={true} /> 两
        </p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-info-border)', borderStyle: 'solid', backgroundColor: 'var(--color-info-soft)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-info-text)' }}>
          <Users className="h-4 w-4" />
          <span>全国人口</span>
        </div>
        <p className="mt-2 text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={overview.population} delta={overview.population_delta} format={true} />{' '}
          人
        </p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <MapPin className="h-4 w-4" />
          <span>省份数量</span>
        </div>
        <p className="mt-2 text-xl font-semibold" style={{ color: 'var(--color-text)' }}>{overview.province_count} 个</p>
      </div>
    </div>
  );
}

import { Coins, MapPin, Users } from 'lucide-react';

import { useEmpireStore } from '../../stores/empireStore';
import { DeltaValue } from './DeltaValue';

export function OverviewPanel() {
  const overview = useEmpireStore((s) => s.overview);

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
        <div className="flex items-center gap-2 text-xs text-amber-700">
          <Coins className="h-4 w-4" />
          <span>国库资金</span>
        </div>
        <p className="mt-2 text-xl font-semibold">
          <DeltaValue value={overview.treasury} delta={overview.treasury_delta} format={true} /> 两
        </p>
      </div>

      <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
        <div className="flex items-center gap-2 text-xs text-blue-700">
          <Users className="h-4 w-4" />
          <span>全国人口</span>
        </div>
        <p className="mt-2 text-xl font-semibold">
          <DeltaValue value={overview.population} delta={overview.population_delta} format={true} />{' '}
          人
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <MapPin className="h-4 w-4" />
          <span>省份数量</span>
        </div>
        <p className="mt-2 text-xl font-semibold">{overview.province_count} 个</p>
      </div>
    </div>
  );
}

import { ChevronDown, Coins, MapPin, Users } from 'lucide-react';

import { useEmpireStore } from '../../stores/empireStore';
import type { ProvinceData } from '../../api/types';
import { DeltaValue } from './DeltaValue';
import { IncidentEffect } from './IncidentEffect';

export function ProvincePanel() {
  const { fullState, selectedProvinceId, setSelectedProvinceId } = useEmpireStore();

  return (
    <div className="space-y-3 p-4 h-full overflow-y-auto">
      <div className="relative">
        <select
          value={selectedProvinceId}
          onChange={(e) => setSelectedProvinceId(e.target.value)}
          className="w-full appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2 pr-8 text-sm focus:border-blue-300 focus:outline-none"
        >
          {fullState?.provinces &&
            Object.entries(fullState.provinces).map(([id, province]) => (
              <option key={id} value={id}>
                {province.name}
              </option>
            ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
      </div>

      {fullState?.provinces && fullState.provinces[selectedProvinceId] && (
        <ProvinceDetails province={fullState.provinces[selectedProvinceId] as ProvinceData} />
      )}
    </div>
  );
}

function ProvinceDetails({ province: p }: { province: ProvinceData }) {
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-purple-100 bg-purple-50 p-3">
        <div className="flex items-center gap-2 text-xs text-purple-700">
          <MapPin className="h-4 w-4" />
          <span>省份名称</span>
        </div>
        <p className="mt-2 text-lg font-semibold">{p.name}</p>
      </div>

      <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
        <div className="flex items-center gap-2 text-xs text-amber-700">
          <Coins className="h-4 w-4" />
          <span>产值</span>
        </div>
        <p className="mt-2 text-lg font-semibold">
          <DeltaValue value={Number(p.production_value)} delta={p.production_value_delta} />
        </p>
      </div>

      <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
        <div className="flex items-center gap-2 text-xs text-blue-700">
          <Users className="h-4 w-4" />
          <span>人口</span>
        </div>
        <p className="mt-2 text-lg font-semibold">
          <DeltaValue value={Number(p.population)} delta={p.population_delta} />
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Coins className="h-4 w-4" />
          <span>库存</span>
        </div>
        <p className="mt-2 text-lg font-semibold">
          <DeltaValue value={Number(p.stockpile)} delta={p.stockpile_delta} />
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="font-mono">💰</span>
          <span>固定支出</span>
        </div>
        <p className="mt-2 text-lg font-semibold">
          <DeltaValue value={Number(p.fixed_expenditure)} delta={p.fixed_expenditure_delta} />
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-green-100 bg-green-50 p-3">
          <div className="text-xs text-green-700">产值增长率</div>
          <p className="mt-1 text-sm font-semibold">
            <IncidentEffect
              value={Number(p.base_production_growth || 0) * 100}
              incidentEffect={p.production_growth_incident}
            />
          </p>
        </div>
        <div className="rounded-xl border border-cyan-100 bg-cyan-50 p-3">
          <div className="text-xs text-cyan-700">人口增长率</div>
          <p className="mt-1 text-sm font-semibold">
            <IncidentEffect
              value={Number(p.base_population_growth || 0) * 100}
              incidentEffect={p.population_growth_incident}
            />
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-orange-100 bg-orange-50 p-3">
        <div className="flex items-center gap-2 text-xs text-orange-700">
          <span className="font-mono">%</span>
          <span>税率</span>
        </div>
        <p className="mt-2 text-lg font-semibold">
          <IncidentEffect
            value={Number(p.actual_tax_rate || 0.1) * 100}
            incidentEffect={p.tax_modifier_incident}
          />
        </p>
      </div>
    </div>
  );
}

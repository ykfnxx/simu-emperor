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
          className="w-full appearance-none rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none"
          style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)', color: 'var(--color-text)' }}
        >
          {fullState?.provinces &&
            Object.entries(fullState.provinces).map(([id, province]) => (
              <option key={id} value={id}>
                {province.name}
              </option>
            ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--color-text-muted)' }} />
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
      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-province-name-border)', borderStyle: 'solid', backgroundColor: 'var(--color-province-name-bg)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-province-name-text)' }}>
          <MapPin className="h-4 w-4" />
          <span>省份名称</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>{p.name}</p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-warning-border)', borderStyle: 'solid', backgroundColor: 'var(--color-warning-soft)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-warning-text)' }}>
          <Coins className="h-4 w-4" />
          <span>产值</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={Number(p.production_value)} delta={p.production_value_delta} />
        </p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-info-border)', borderStyle: 'solid', backgroundColor: 'var(--color-info-soft)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-info-text)' }}>
          <Users className="h-4 w-4" />
          <span>人口</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={Number(p.population)} delta={p.population_delta} />
        </p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <Coins className="h-4 w-4" />
          <span>库存</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={Number(p.stockpile)} delta={p.stockpile_delta} />
        </p>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          <span className="font-mono">💰</span>
          <span>固定支出</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          <DeltaValue value={Number(p.fixed_expenditure)} delta={p.fixed_expenditure_delta} />
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-province-green-border)', borderStyle: 'solid', backgroundColor: 'var(--color-province-green-bg)' }}>
          <div className="text-xs" style={{ color: 'var(--color-province-green-text)' }}>产值增长率</div>
          <p className="mt-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            <IncidentEffect
              value={Number(p.base_production_growth || 0) * 100}
              incidentEffect={p.production_growth_incident}
            />
          </p>
        </div>
        <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-province-cyan-border)', borderStyle: 'solid', backgroundColor: 'var(--color-province-cyan-bg)' }}>
          <div className="text-xs" style={{ color: 'var(--color-province-cyan-text)' }}>人口增长率</div>
          <p className="mt-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            <IncidentEffect
              value={Number(p.base_population_growth || 0) * 100}
              incidentEffect={p.population_growth_incident}
            />
          </p>
        </div>
      </div>

      <div className="rounded-xl p-3" style={{ borderWidth: 1, borderColor: 'var(--color-province-orange-border)', borderStyle: 'solid', backgroundColor: 'var(--color-province-orange-bg)' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-province-orange-text)' }}>
          <span className="font-mono">%</span>
          <span>税率</span>
        </div>
        <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          <IncidentEffect
            value={Number(p.actual_tax_rate || 0.1) * 100}
            incidentEffect={p.tax_modifier_incident}
          />
        </p>
      </div>
    </div>
  );
}

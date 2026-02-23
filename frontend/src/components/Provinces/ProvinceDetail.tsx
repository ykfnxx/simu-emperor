import { ArrowLeft, Users, Wheat, Coins, Heart, Swords, ShoppingCart, ScrollText } from 'lucide-react'
import { useGameStore } from '../../stores/gameStore'
import type { ProvinceBaseData } from '../../types'

interface ProvinceDetailProps {
  province: ProvinceBaseData
  onBack: () => void
}

export function ProvinceDetail({ province, onBack }: ProvinceDetailProps) {
  const { active_events } = useGameStore()
  const formatNumber = (num: number) => num.toLocaleString()

  // 筛选与该省份相关的事件
  const provinceEvents = active_events.filter(
    (e) => e.target_province_id === province.province_id
  )

  const StatRow = ({ label, value, unit }: { label: string; value: string | number; unit?: string }) => (
    <div className="flex justify-between py-2 border-b border-gray-100">
      <span className="text-gray-600">{label}</span>
      <span className="font-medium">
        {value}
        {unit && <span className="text-gray-400 ml-1">{unit}</span>}
      </span>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft size={20} />
        </button>
        <h2 className="text-2xl font-bold text-gray-900">{province.name}</h2>
      </div>

      {/* Province Events */}
      {provinceEvents.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <ScrollText className="text-amber-600" size={20} />
            <h3 className="text-lg font-semibold">当前政令 ({provinceEvents.length})</h3>
          </div>
          <div className="space-y-2">
            {provinceEvents.map((event) => (
              <div
                key={event.event_id}
                className="p-3 bg-amber-50 rounded-lg border border-amber-200"
              >
                <p className="text-gray-900">{event.description}</p>
                <p className="text-sm text-gray-500 mt-1">
                  类型: {event.command_type || event.source}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Population */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Users className="text-blue-600" size={20} />
            <h3 className="text-lg font-semibold">人口</h3>
          </div>
          <StatRow label="总人口" value={formatNumber(Number(province.population.total))} />
          <StatRow label="增长率" value={`${(Number(province.population.growth_rate) * 100).toFixed(2)}%`} />
          <StatRow label="劳力比例" value={`${(Number(province.population.labor_ratio) * 100).toFixed(0)}%`} />
          <StatRow label="民心" value={`${(Number(province.population.happiness) * 100).toFixed(0)}%`} />
        </div>

        {/* Agriculture */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Wheat className="text-amber-600" size={20} />
            <h3 className="text-lg font-semibold">农业</h3>
          </div>
          <StatRow label="粮仓储粮" value={formatNumber(Number(province.granary_stock))} unit="石" />
          <StatRow label="灌溉水平" value={`${(Number(province.agriculture.irrigation_level) * 100).toFixed(0)}%`} />
          <StatRow label="作物种类" value={province.agriculture.crops.length} />
        </div>

        {/* Commerce */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShoppingCart className="text-green-600" size={20} />
            <h3 className="text-lg font-semibold">商业与贸易</h3>
          </div>
          <StatRow label="商户户数" value={formatNumber(Number(province.commerce.merchant_households))} />
          <StatRow label="市场繁荣" value={`${(Number(province.commerce.market_prosperity) * 100).toFixed(0)}%`} />
          <StatRow label="贸易量" value={formatNumber(Number(province.trade.trade_volume))} />
          <StatRow label="商路质量" value={`${(Number(province.trade.trade_route_quality) * 100).toFixed(0)}%`} />
        </div>

        {/* Military */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Swords className="text-red-600" size={20} />
            <h3 className="text-lg font-semibold">军事</h3>
          </div>
          <StatRow label="驻军规模" value={formatNumber(Number(province.military.garrison_size))} />
          <StatRow label="装备水平" value={`${(Number(province.military.equipment_level) * 100).toFixed(0)}%`} />
          <StatRow label="士气" value={`${(Number(province.military.morale) * 100).toFixed(0)}%`} />
          <StatRow label="军费" value={formatNumber(Number(province.military.upkeep))} unit="两" />
        </div>

        {/* Taxation */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Coins className="text-purple-600" size={20} />
            <h3 className="text-lg font-semibold">赋税</h3>
          </div>
          <StatRow label="田赋率" value={`${(Number(province.taxation.land_tax_rate) * 100).toFixed(1)}%`} />
          <StatRow label="商税率" value={`${(Number(province.taxation.commercial_tax_rate) * 100).toFixed(1)}%`} />
          <StatRow label="关税率" value={`${(Number(province.taxation.tariff_rate) * 100).toFixed(1)}%`} />
          <StatRow label="地方府库" value={formatNumber(Number(province.local_treasury))} unit="两" />
        </div>

        {/* Administration */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Heart className="text-pink-600" size={20} />
            <h3 className="text-lg font-semibold">行政</h3>
          </div>
          <StatRow label="官员数量" value={formatNumber(Number(province.administration.official_count))} />
          <StatRow label="官员俸禄" value={formatNumber(Number(province.administration.official_salary))} unit="两/年" />
          <StatRow label="基建价值" value={formatNumber(Number(province.administration.infrastructure_value))} unit="两" />
          <StatRow label="朝廷征调" value={formatNumber(Number(province.administration.court_levy_amount))} unit="两" />
        </div>
      </div>
    </div>
  )
}

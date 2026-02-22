import { ArrowLeft, Users, Wheat, Coins, Heart, Swords, ShoppingCart } from 'lucide-react'
import type { ProvinceBaseData } from '../../types'

interface ProvinceDetailProps {
  province: ProvinceBaseData
  onBack: () => void
}

export function ProvinceDetail({ province, onBack }: ProvinceDetailProps) {
  const formatNumber = (num: number) => num.toLocaleString()

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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Population */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Users className="text-blue-600" size={20} />
            <h3 className="text-lg font-semibold">Population</h3>
          </div>
          <StatRow label="Total" value={formatNumber(Number(province.population.total))} />
          <StatRow label="Growth Rate" value={`${(Number(province.population.growth_rate) * 100).toFixed(2)}%`} />
          <StatRow label="Labor Ratio" value={`${(Number(province.population.labor_ratio) * 100).toFixed(0)}%`} />
          <StatRow label="Happiness" value={`${(Number(province.population.happiness) * 100).toFixed(0)}%`} />
        </div>

        {/* Agriculture */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Wheat className="text-amber-600" size={20} />
            <h3 className="text-lg font-semibold">Agriculture</h3>
          </div>
          <StatRow label="Granary Stock" value={formatNumber(Number(province.granary_stock))} unit="shi" />
          <StatRow label="Irrigation Level" value={`${(Number(province.agriculture.irrigation_level) * 100).toFixed(0)}%`} />
          <StatRow label="Crop Types" value={province.agriculture.crops.length} />
        </div>

        {/* Commerce */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShoppingCart className="text-green-600" size={20} />
            <h3 className="text-lg font-semibold">Commerce & Trade</h3>
          </div>
          <StatRow label="Merchant Households" value={formatNumber(Number(province.commerce.merchant_households))} />
          <StatRow label="Market Prosperity" value={`${(Number(province.commerce.market_prosperity) * 100).toFixed(0)}%`} />
          <StatRow label="Trade Volume" value={formatNumber(Number(province.trade.trade_volume))} />
          <StatRow label="Trade Route Quality" value={`${(Number(province.trade.trade_route_quality) * 100).toFixed(0)}%`} />
        </div>

        {/* Military */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Swords className="text-red-600" size={20} />
            <h3 className="text-lg font-semibold">Military</h3>
          </div>
          <StatRow label="Garrison Size" value={formatNumber(Number(province.military.garrison_size))} />
          <StatRow label="Equipment Level" value={`${(Number(province.military.equipment_level) * 100).toFixed(0)}%`} />
          <StatRow label="Morale" value={`${(Number(province.military.morale) * 100).toFixed(0)}%`} />
          <StatRow label="Upkeep" value={formatNumber(Number(province.military.upkeep))} unit="taels" />
        </div>

        {/* Taxation */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Coins className="text-purple-600" size={20} />
            <h3 className="text-lg font-semibold">Taxation</h3>
          </div>
          <StatRow label="Land Tax Rate" value={`${(Number(province.taxation.land_tax_rate) * 100).toFixed(1)}%`} />
          <StatRow label="Commercial Tax Rate" value={`${(Number(province.taxation.commercial_tax_rate) * 100).toFixed(1)}%`} />
          <StatRow label="Tariff Rate" value={`${(Number(province.taxation.tariff_rate) * 100).toFixed(1)}%`} />
          <StatRow label="Local Treasury" value={formatNumber(Number(province.local_treasury))} unit="taels" />
        </div>

        {/* Administration */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Heart className="text-pink-600" size={20} />
            <h3 className="text-lg font-semibold">Administration</h3>
          </div>
          <StatRow label="Official Count" value={formatNumber(Number(province.administration.official_count))} />
          <StatRow label="Official Salary" value={formatNumber(Number(province.administration.official_salary))} unit="taels/yr" />
          <StatRow label="Infrastructure Value" value={formatNumber(Number(province.administration.infrastructure_value))} unit="taels" />
          <StatRow label="Court Levy" value={formatNumber(Number(province.administration.court_levy_amount))} unit="taels" />
        </div>
      </div>
    </div>
  )
}

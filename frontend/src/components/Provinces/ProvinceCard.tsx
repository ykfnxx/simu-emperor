import { Users, Wheat, Coins, Heart } from 'lucide-react'
import type { ProvinceBaseData } from '../../types'

interface ProvinceCardProps {
  province: ProvinceBaseData
  onClick: () => void
}

export function ProvinceCard({ province, onClick }: ProvinceCardProps) {
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const happiness = Number(province.population.happiness)
  const happinessColor =
    happiness > 0.6 ? 'text-green-600' : happiness > 0.4 ? 'text-yellow-600' : 'text-red-600'

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow"
    >
      <h3 className="text-lg font-semibold text-gray-900 mb-3">{province.name}</h3>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex items-center gap-2 text-gray-600">
          <Users size={16} />
          <span className="text-sm">{formatNumber(Number(province.population.total))}</span>
        </div>

        <div className="flex items-center gap-2 text-gray-600">
          <Wheat size={16} />
          <span className="text-sm">{formatNumber(Number(province.granary_stock))}</span>
        </div>

        <div className="flex items-center gap-2 text-gray-600">
          <Coins size={16} />
          <span className="text-sm">{formatNumber(Number(province.local_treasury))}</span>
        </div>

        <div className={`flex items-center gap-2 ${happinessColor}`}>
          <Heart size={16} />
          <span className="text-sm">{(happiness * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-100">
        <div className="flex justify-between text-xs text-gray-500">
          <span>Garrison: {formatNumber(Number(province.military.garrison_size))}</span>
          <span>Commerce: {(Number(province.commerce.market_prosperity) * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  )
}

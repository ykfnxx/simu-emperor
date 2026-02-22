import { AlertTriangle, Wheat, Swords, Coins } from 'lucide-react'
import type { ProvinceBaseData } from '../../types'

interface UrgentPanelProps {
  provinces: ProvinceBaseData[]
}

interface UrgentItem {
  province: string
  issue: string
  severity: 'high' | 'medium' | 'low'
  icon: typeof AlertTriangle
}

export function UrgentPanel({ provinces }: UrgentPanelProps) {
  const urgentItems: UrgentItem[] = []

  // Check for urgent issues
  provinces.forEach((province) => {
    // Low happiness
    if (province.population.happiness < 0.4) {
      urgentItems.push({
        province: province.name,
        issue: 'Happiness critically low',
        severity: 'high',
        icon: AlertTriangle,
      })
    }

    // Low granary
    const grainNeed =
      Number(province.population.total) *
      Number(province.consumption.civilian_grain_per_capita)
    if (Number(province.granary_stock) < grainNeed * 0.2) {
      urgentItems.push({
        province: province.name,
        issue: 'Granary nearly empty',
        severity: 'high',
        icon: Wheat,
      })
    }

    // Low morale
    if (province.military.morale < 0.4) {
      urgentItems.push({
        province: province.name,
        issue: 'Military morale low',
        severity: 'medium',
        icon: Swords,
      })
    }

    // Low treasury
    if (Number(province.local_treasury) < 1000) {
      urgentItems.push({
        province: province.name,
        issue: 'Local treasury depleted',
        severity: 'low',
        icon: Coins,
      })
    }
  })

  if (urgentItems.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        <p>No urgent matters at this time</p>
      </div>
    )
  }

  const severityColors = {
    high: 'bg-red-50 border-red-300 text-red-800',
    medium: 'bg-yellow-50 border-yellow-300 text-yellow-800',
    low: 'bg-gray-50 border-gray-300 text-gray-800',
  }

  return (
    <div className="space-y-2">
      {urgentItems.map((item, index) => {
        const Icon = item.icon
        return (
          <div
            key={index}
            className={`flex items-center gap-3 p-3 rounded border ${severityColors[item.severity]}`}
          >
            <Icon size={20} />
            <div>
              <p className="font-medium">{item.province}</p>
              <p className="text-sm opacity-75">{item.issue}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

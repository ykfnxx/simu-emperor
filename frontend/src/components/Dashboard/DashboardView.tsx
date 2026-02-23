import { useEffect } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { Loading } from '../common/Loading'
import { TrendChart } from './TrendChart'
import { UrgentPanel } from './UrgentPanel'
import { StatHeader } from '../Layout/StatHeader'
import { ScrollText, User, MapPin } from 'lucide-react'

const PHASE_LABELS: Record<string, string> = {
  RESOLUTION: '结算',
  SUMMARY: '汇总',
  INTERACTION: '交互',
  EXECUTION: '执行',
}

export function DashboardView() {
  const { turn, phase, provinces, imperial_treasury, active_events, isLoading, error, fetchState } =
    useGameStore()

  useEffect(() => {
    fetchState()
  }, [fetchState])

  if (isLoading && provinces.length === 0) {
    return <Loading text="加载中..." />
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        <p>错误: {error}</p>
        <button
          onClick={fetchState}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          重试
        </button>
      </div>
    )
  }

  // Calculate summary stats
  const totalPopulation = provinces.reduce(
    (sum, p) => sum + Number(p.population.total),
    0
  )
  const totalMilitary = provinces.reduce(
    (sum, p) => sum + Number(p.military.garrison_size),
    0
  )
  const avgHappiness =
    provinces.length > 0
      ? provinces.reduce((sum, p) => sum + Number(p.population.happiness), 0) /
        provinces.length
      : 0

  return (
    <div className="space-y-6">
      <StatHeader
        title="龙椅"
        stats={[
          { label: '人口', value: totalPopulation.toLocaleString() },
          { label: '兵力', value: totalMilitary.toLocaleString() },
          {
            label: '民心',
            value: `${(avgHappiness * 100).toFixed(1)}%`,
            color: avgHappiness > 0.6 ? 'text-green-600' : 'text-red-600',
          },
        ]}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="国库"
          value={`${imperial_treasury.toLocaleString()} 两`}
          color="amber"
        />
        <SummaryCard
          title="省份"
          value={provinces.length.toString()}
          color="blue"
        />
        <SummaryCard
          title="当前回合"
          value={turn.toString()}
          color="purple"
        />
        <SummaryCard
          title="当前阶段"
          value={PHASE_LABELS[phase] || phase}
          color="green"
        />
      </div>

      {/* Active Events */}
      {active_events.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ScrollText className="text-amber-600" size={20} />
            当前期政 ({active_events.length})
          </h3>
          <div className="space-y-2">
            {active_events.map((event) => (
              <div
                key={event.event_id}
                className="flex items-center gap-3 p-3 bg-amber-50 rounded-lg border border-amber-200"
              >
                {event.source === 'player' && (
                  <User className="text-amber-600" size={18} />
                )}
                {event.target_province_id && (
                  <MapPin className="text-gray-400" size={16} />
                )}
                <div className="flex-1">
                  <p className="text-gray-900">{event.description}</p>
                  {event.target_province_id && (
                    <p className="text-sm text-gray-500">
                      目标: {event.target_province_id}
                    </p>
                  )}
                </div>
                <span className="text-xs px-2 py-1 bg-amber-100 text-amber-800 rounded">
                  {event.command_type || event.source}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">国势走向</h3>
          <TrendChart />
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">紧急事项</h3>
          <UrgentPanel provinces={provinces} />
        </div>
      </div>
    </div>
  )
}

interface SummaryCardProps {
  title: string
  value: string
  color: 'amber' | 'blue' | 'purple' | 'green'
}

const colorClasses = {
  amber: 'bg-amber-50 border-amber-200 text-amber-800',
  blue: 'bg-blue-50 border-blue-200 text-blue-800',
  purple: 'bg-purple-50 border-purple-200 text-purple-800',
  green: 'bg-green-50 border-green-200 text-green-800',
}

function SummaryCard({ title, value, color }: SummaryCardProps) {
  return (
    <div className={`p-4 rounded-lg border ${colorClasses[color]}`}>
      <p className="text-sm opacity-75">{title}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}

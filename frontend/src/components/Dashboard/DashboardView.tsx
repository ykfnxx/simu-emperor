import { useEffect } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { Loading } from '../common/Loading'
import { TrendChart } from './TrendChart'
import { UrgentPanel } from './UrgentPanel'
import { StatHeader } from '../Layout/StatHeader'

export function DashboardView() {
  const { turn, phase, provinces, imperial_treasury, isLoading, error, fetchState } =
    useGameStore()

  useEffect(() => {
    fetchState()
  }, [fetchState])

  if (isLoading && provinces.length === 0) {
    return <Loading text="Loading game state..." />
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        <p>Error: {error}</p>
        <button
          onClick={fetchState}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
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
        title="Dashboard"
        stats={[
          { label: 'Population', value: totalPopulation.toLocaleString() },
          { label: 'Military', value: totalMilitary.toLocaleString() },
          {
            label: 'Happiness',
            value: `${(avgHappiness * 100).toFixed(1)}%`,
            color: avgHappiness > 0.6 ? 'text-green-600' : 'text-red-600',
          },
        ]}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Imperial Treasury"
          value={`${imperial_treasury.toLocaleString()} taels`}
          color="amber"
        />
        <SummaryCard
          title="Provinces"
          value={provinces.length.toString()}
          color="blue"
        />
        <SummaryCard
          title="Current Turn"
          value={turn.toString()}
          color="purple"
        />
        <SummaryCard
          title="Phase"
          value={phase}
          color="green"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">National Trend</h3>
          <TrendChart />
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Urgent Matters</h3>
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

import { useState } from 'react'
import { Loading } from '../common/Loading'
import { MemorialCard } from './MemorialCard'
import type { ReportResponse } from '../../types'

// Mock data for now - will be replaced with API calls
const mockReports: ReportResponse[] = [
  {
    agent_id: 'minister_of_revenue',
    turn: 1,
    markdown: `# Ministry of Revenue Report - Turn 1

## Tax Collection Summary
- Land tax collected: 150,000 taels
- Commercial tax: 45,000 taels
- Tariffs: 12,000 taels

## Recommendations
The treasury is healthy. I recommend investing in irrigation infrastructure.`,
  },
  {
    agent_id: 'minister_of_war',
    turn: 1,
    markdown: `# Ministry of War Report - Turn 1

## Military Status
- Total garrison: 50,000 troops
- Equipment level: 75%
- Average morale: 82%

## Concerns
Northern border reports increased bandit activity.`,
  },
]

export function MemorialView() {
  const [selectedTurn, setSelectedTurn] = useState(1)
  const [isLoading] = useState(false)

  if (isLoading) {
    return <Loading text="Loading memorials..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Memorials</h2>
        <div className="flex items-center gap-2">
          <label className="text-gray-500">Turn:</label>
          <select
            value={selectedTurn}
            onChange={(e) => setSelectedTurn(Number(e.target.value))}
            className="px-3 py-1 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
          >
            <option value={1}>Turn 1</option>
            <option value={2}>Turn 2</option>
            <option value={3}>Turn 3</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {mockReports.map((report, index) => (
          <MemorialCard key={index} report={report} />
        ))}
      </div>

      {mockReports.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          <p>No memorials for this turn</p>
        </div>
      )}
    </div>
  )
}

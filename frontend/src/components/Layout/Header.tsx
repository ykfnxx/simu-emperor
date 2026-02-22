import { Play, Loader2 } from 'lucide-react'
import { useGameStore } from '../../stores/gameStore'

export function Header() {
  const { turn, phase, imperial_treasury, isLoading, advanceTurn } =
    useGameStore()

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  const phaseLabels: Record<string, string> = {
    RESOLUTION: 'Resolution',
    SUMMARY: 'Summary',
    INTERACTION: 'Interaction',
    EXECUTION: 'Execution',
  }

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      {/* Left: Turn Info */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-gray-500 text-sm">Turn</span>
          <span className="text-2xl font-bold text-amber-900">{turn}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500 text-sm">Phase</span>
          <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium">
            {phaseLabels[phase] || phase}
          </span>
        </div>
      </div>

      {/* Right: Treasury & Advance */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-gray-500 text-sm">Treasury</span>
          <span className="text-lg font-semibold text-amber-700">
            {formatNumber(imperial_treasury)} taels
          </span>
        </div>
        <button
          onClick={advanceTurn}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Play size={18} />
          )}
          <span>Advance</span>
        </button>
      </div>
    </header>
  )
}

import { useState } from 'react'
import { useGameStore } from '../../stores/gameStore'
import { Loading } from '../common/Loading'
import { ProvinceCard } from './ProvinceCard'
import { ProvinceDetail } from './ProvinceDetail'
import type { ProvinceBaseData } from '../../types'

export function ProvincesView() {
  const { provinces, isLoading, error, fetchState } = useGameStore()
  const [selectedProvince, setSelectedProvince] = useState<ProvinceBaseData | null>(null)

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

  if (selectedProvince) {
    return (
      <ProvinceDetail
        province={selectedProvince}
        onBack={() => setSelectedProvince(null)}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">疆域</h2>
        <p className="text-gray-500">共 {provinces.length} 个省份</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {provinces.map((province) => (
          <ProvinceCard
            key={province.province_id}
            province={province}
            onClick={() => setSelectedProvince(province)}
          />
        ))}
      </div>
    </div>
  )
}

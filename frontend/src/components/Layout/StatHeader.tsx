interface StatHeaderProps {
  title: string
  stats?: Array<{
    label: string
    value: string | number
    color?: string
  }>
}

export function StatHeader({ title, stats = [] }: StatHeaderProps) {
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
        {stats.length > 0 && (
          <div className="flex items-center gap-6">
            {stats.map((stat, index) => (
              <div key={index} className="flex items-center gap-2">
                <span className="text-gray-500 text-sm">{stat.label}</span>
                <span className={`font-semibold ${stat.color || 'text-gray-900'}`}>
                  {stat.value}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

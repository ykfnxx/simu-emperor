import { Loader2 } from 'lucide-react'

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg'
  text?: string
}

const sizeMap = {
  sm: 16,
  md: 24,
  lg: 32,
}

export function Loading({ size = 'md', text }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <Loader2
        size={sizeMap[size]}
        className="animate-spin text-amber-600"
      />
      {text && <p className="mt-2 text-gray-500 text-sm">{text}</p>}
    </div>
  )
}

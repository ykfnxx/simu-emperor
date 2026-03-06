import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">皇帝模拟器 V2 - Web 前端</h1>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="mb-4">前端项目已初始化成功！</p>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setCount((count) => count + 1)}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Count is {count}
            </button>
          </div>
          <div className="mt-4 text-sm text-gray-600">
            <p>✅ Vite + React + TypeScript 配置完成</p>
            <p>✅ 目录结构创建完成</p>
            <p>⏳ 等待依赖安装...</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

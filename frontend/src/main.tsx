import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// 清除前端缓存（每次启动时清除 localStorage）
const CACHE_KEY = 'simu-emperor-cache-cleared'
const CURRENT_VERSION = '2026-02-23' // 更新此版本号以触发缓存清理

const storedVersion = localStorage.getItem(CACHE_KEY)
if (storedVersion !== CURRENT_VERSION) {
  console.log('Clearing frontend cache...')
  localStorage.clear()
  localStorage.setItem(CACHE_KEY, CURRENT_VERSION)
  console.log('Frontend cache cleared.')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

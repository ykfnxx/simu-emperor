import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// 每次启动清除前端缓存（聊天记录存储在 localStorage）
console.log('Clearing frontend cache...')
localStorage.clear()
console.log('Frontend cache cleared.')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 代理 API 请求到后端
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'http://localhost:8000',
        ws: true
      }
    }
  },
  build: {
    outDir: '../src/simu_emperor/adapters/web/static',
    emptyOutDir: true
  }
})

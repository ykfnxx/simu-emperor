import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const backendPort = Number(process.env.PORT ?? 8787);
const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  root: resolve(import.meta.dirname, 'web'),
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: Number(process.env.VITE_DEV_PORT ?? 5173),
    fs: {
      allow: [resolve(import.meta.dirname)],
    },
    proxy: {
      '/api/': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, 'dist/web'),
    emptyOutDir: true,
  },
});

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // REST API proxy
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Don't crash when backend is offline
        configure: (proxy) => {
          proxy.on('error', () => {})
        },
      },
      // WebSocket proxy
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
        // Silently ignore connection errors when backend is not running
        configure: (proxy) => {
          proxy.on('error', () => {})
          proxy.on('proxyReqWs', () => {})
        },
      },
    },
  },
  build: { outDir: 'dist' },
})

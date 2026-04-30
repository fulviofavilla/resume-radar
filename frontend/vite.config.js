import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/analyze':  'http://localhost:8000',
      '/progress': 'http://localhost:8000',
      '/results':  'http://localhost:8000',
      '/health':   'http://localhost:8000',
    },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})

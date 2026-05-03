import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5100,
    proxy: {
      '/backlog': 'http://localhost:5101',
      '/sessions': 'http://localhost:5101',
      '/timer': 'http://localhost:5101',
      '/tasks': 'http://localhost:5101',
      '/ws': { target: 'ws://localhost:5101', ws: true },
    },
  },
})

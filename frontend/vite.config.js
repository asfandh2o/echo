import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    allowedHosts: true,
    proxy: {
      '/auth/google': 'http://localhost:8000',
      '/emails': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/suggestions': 'http://localhost:8000',
      '/digests': 'http://localhost:8000',
      '/calendar': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/notifications': 'http://localhost:8000',
      '/tasks': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/v1/products': 'http://localhost:8180',
      '/api/v1/orders': 'http://localhost:8181',
      '/api/v1/screens': 'http://localhost:8190',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
  },
})

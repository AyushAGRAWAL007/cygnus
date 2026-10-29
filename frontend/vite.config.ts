import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the browser talks to Vite (port 5173). Vite forwards any
// request starting with /api to the FastAPI server (port 8000), so the
// frontend code never needs to know the backend's address.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})

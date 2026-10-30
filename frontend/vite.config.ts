import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// In development the browser talks to Vite (port 5173). Vite forwards any
// request starting with /api to the FastAPI server (port 8000), so the
// frontend code never needs to know the backend's address.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'CYGNUS_')
  const apiTarget = process.env.CYGNUS_DEV_API_TARGET ?? env.CYGNUS_DEV_API_TARGET ?? 'http://127.0.0.1:8000'
  const backendAddress = new URL(apiTarget).origin
  return {
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('error', (error, _request, response) => {
            if (!('writeHead' in response) || response.headersSent || response.writableEnded) return
            const code = (error as NodeJS.ErrnoException).code
            const detail = code === 'ECONNREFUSED'
              ? `Cannot reach the backend at ${backendAddress}. Start the backend and make sure its port matches the frontend proxy configuration, then retry.`
              : code === 'ETIMEDOUT' || code === 'ESOCKETTIMEDOUT'
                ? `The backend at ${backendAddress} took too long to respond. Check the backend terminal for errors, then retry.`
                : `The connection to the backend at ${backendAddress} failed. Check that the backend is running and review its terminal for errors, then retry.`
            response.writeHead(502, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
            response.end(JSON.stringify({ detail }))
          })
        },
      },
    },
  },
  }
})

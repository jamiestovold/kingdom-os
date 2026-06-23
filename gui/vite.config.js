import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'

function loadKingdomToken() {
  const envPath = '/home/kingdom-os/.env'
  try {
    const env = fs.readFileSync(envPath, 'utf8')
    const line = env.split('\n').find(l => l.startsWith('KINGDOM_API_TOKEN='))
    return line ? line.split('=').slice(1).join('=').trim() : ''
  } catch (e) {
    console.warn('[kingdom] Could not read .env:', e.message)
    return ''
  }
}

const token = loadKingdomToken()
if (!token) console.warn('[kingdom] No KINGDOM_API_TOKEN found -- API calls will fail auth')

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: path => path.replace(/^\/api/, ''),
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    }
  }
})

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = Number(env.MANGO_DEV_PORT) || 5180

  return {
    plugins: [react()],
    server: {
      port,
      strictPort: true,
    },
  }
})

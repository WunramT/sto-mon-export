import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { fileURLToPath, URL } from 'node:url'

// Basis-Pfad: im Container-Build ein Platzhalter, den entrypoint.sh zur Laufzeit ersetzt (ein Build für test/prod)
const getBasePath = (): string => {
  const envPath = process.env.VITE_BASE_PATH
  if (envPath !== undefined) return envPath === '' ? '/' : envPath.endsWith('/') ? envPath : `${envPath}/`
  return '/__VITE_BASE_PATH__/'
}
const basePath = getBasePath()
const backend = process.env.VITE_PROXY_TARGET || 'http://backend:8000'
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export default defineConfig({
  base: basePath,
  plugins: [vue(), vuetify({ autoImport: true })],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': { target: backend, changeOrigin: true, timeout: 600000 },
      ...(basePath !== '/' ? {
        [`${basePath}api/`]: {
          target: backend, changeOrigin: true, timeout: 600000,
          rewrite: (p: string) => p.replace(new RegExp(`^${escape(basePath)}`), '/'),
        },
      } : {}),
    },
  },
  build: { outDir: 'dist', sourcemap: false, minify: 'esbuild', chunkSizeWarningLimit: 1500 },
})

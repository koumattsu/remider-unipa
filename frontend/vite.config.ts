// frontend/vite.config.ts

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '') 
  const apiBase = env.VITE_API_BASE_URL || ''

  return {
    define: {
      'self.__VITE_API_BASE_URL': JSON.stringify(apiBase),
    },
    plugins: [
      react(),
      VitePWA({
        registerType: 'prompt',
        strategies: 'injectManifest',
        srcDir: 'src',
        filename: 'sw.ts',

        includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
        manifest: {
          name: 'DueFlow',
          short_name: 'DueFlow',
          start_url: '/#/dashboard',
          display: 'standalone',
          background_color: '#0b0f1a',
          theme_color: '#0b0f1a',
          icons: [
            { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          ],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
  }
})

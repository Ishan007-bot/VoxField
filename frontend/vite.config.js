import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'VoxField — Voice Field Assistant',
        short_name: 'VoxField',
        description: 'Hands-free voice assistant for industrial field technicians.',
        theme_color: '#0c1014',
        background_color: '#0c1014',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        // Cache the app shell so it loads offline; API calls handled by our own queue.
        navigateFallback: '/index.html',
        globPatterns: ['**/*.{js,css,html,svg,png}'],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // Dev convenience: forward /api to the FastAPI backend.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
    },
  },
})

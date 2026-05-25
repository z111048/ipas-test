import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: process.env.VITE_BASE_URL ?? '/',
  build: {
    outDir: resolve(__dirname, '../docs'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          return 'vendor'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@data': resolve(__dirname, '../data/初級'),
      '@data-mid': resolve(__dirname, '../data/中級'),
    },
  },
})

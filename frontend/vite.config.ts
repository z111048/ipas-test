import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

const externalAssetBase = process.env.VITE_ASSET_BASE_URL?.trim()

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: process.env.VITE_BASE_URL ?? '/',
  // 圖片已驗證並由外部資產站提供時，不要再把 400+ MB 的同一份檔案複製進
  // GitHub Pages artifact。public-shell 只保留應用程式本身仍需提供的小檔案。
  publicDir: resolve(__dirname, externalAssetBase ? 'public-shell' : 'public'),
  build: {
    outDir: resolve(__dirname, '../docs'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 650,
    // Route components already use dynamic imports. Let Rollup derive their shared
    // chunks from the actual import graph; a catch-all vendor chunk makes the entry
    // preload route-only Markdown, syntax-highlighting, and 3D dependencies.
  },
  resolve: {
    alias: {
      '@catalog': resolve(__dirname, '../data'),
      '@data': resolve(__dirname, '../data/初級'),
      '@data-mid': resolve(__dirname, '../data/中級'),
    },
  },
})

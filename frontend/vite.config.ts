import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

// canonical 與分享預覽圖（og:image）必須是絕對網址，index.html 以 %VITE_SITE_URL% 置換。
// 兩個部署（Render、GitHub Pages）都宣告 Render 正式站為唯一的正式網址，讓搜尋引擎只收錄一個；
// 要改正式網址時改這裡，或在建置環境設定 VITE_SITE_URL。
process.env.VITE_SITE_URL ??= 'https://ipas-test.onrender.com'

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
    // 這次只拆框架核心（react、router）：它們很少變動，部署後回訪者不必重抓框架。
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|@remix-run\/router)\//.test(id)) {
            return 'vendor'
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@catalog': resolve(__dirname, '../data'),
      '@data': resolve(__dirname, '../data/初級'),
      '@data-mid': resolve(__dirname, '../data/中級'),
    },
  },
})

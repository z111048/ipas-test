import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

const GRAPH_3D_PACKAGES = [
  'three', 'three-spritetext', 'three-forcegraph', 'three-render-objects',
  '3d-force-graph', 'react-force-graph-3d',
  // d3 全套都只是力導向圖的相依，這個前端本來一支 d3 都沒有
  'd3-force-3d', 'd3-binarytree', 'd3-octree', 'd3-quadtree', 'd3-array', 'd3-color',
  'd3-dispatch', 'd3-format', 'd3-interpolate', 'd3-scale', 'd3-scale-chromatic',
  'd3-selection', 'd3-time', 'd3-time-format', 'd3-timer',
  'kapsule', 'accessor-fn', 'float-tooltip', 'index-array-by',
  'ngraph.events', 'ngraph.forcelayout', 'ngraph.graph', 'ngraph.merge', 'ngraph.random',
  '@tweenjs/tween.js',
  // polished / tinycolor2 / lodash-es 也是這次才進來的（force-graph 的相依）
  'polished', 'tinycolor2', 'lodash-es',
]

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
          // three.js 與力導向圖只有 /concepts 的立體圖用得到（約 1.3MB）。
          // 丟進共用的 vendor 會讓每一頁都下載它，lazy import 就白做了。
          // 用精確的套件名單而不是寬鬆的樣式：`d3-*` 之類的寬樣式會把 vendor 也
          // 用到的套件切過來，rollup 會警告 graph3d ↔ vendor 循環。
          if (GRAPH_3D_PACKAGES.some((name) => id.includes(`node_modules/${name}/`))) {
            // 交給 Vite 自動切：它會把只被 lazy import 用到的模組放進那個 async chunk。
            // 自己命名一個 'graph3d' chunk 反而會做出 vendor ↔ graph3d 的循環
            // （vendor 裡有一個模組也用到其中一支），結果每一頁都下載這 1.3MB。
            return undefined
          }
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

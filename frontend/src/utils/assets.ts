const viteBase = import.meta.env.BASE_URL || '/'

/**
 * 靜態資產的外部來源（例如 Cloudflare R2 的自訂網域）。
 *
 * 資料 JSON 裡存的一律是根相對路徑（`/pdf-assets/中級/guide1/page_000/page.png`），
 * 這是刻意的——資產換 host 時只要改這一個環境變數，2000 多筆資料一個字都不用動。
 * 對應的後端慣例在 `scripts/asset_paths.py`。
 */
const assetBase = (import.meta.env.VITE_ASSET_BASE_URL ?? '').trim().replace(/\/+$/, '')

function inferredPathBase() {
  if (typeof window === 'undefined') return ''
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') return ''
  if (!window.location.hostname.endsWith('github.io')) return ''
  const firstSegment = window.location.pathname.split('/').filter(Boolean)[0]
  return firstSegment ? `/${firstSegment}` : ''
}

export function publicAsset(path: string) {
  const cleanPath = path.replace(/^\/+/, '')
  // 設了外部來源就直接用它，不要再疊 vite base——那是「資產由本站提供」時才需要的前綴。
  if (assetBase) return `${assetBase}/${cleanPath}`
  const configuredBase = viteBase.replace(/\/$/, '')
  const base = configuredBase && configuredBase !== '/' ? configuredBase : inferredPathBase()
  return base ? `${base}/${cleanPath}` : `/${cleanPath}`
}

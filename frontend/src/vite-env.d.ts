/// <reference types="vite/client" />

/**
 * 自訂環境變數的型別宣告。
 *
 * 用途是**讓變數有型別與說明**，不是防止拼錯：
 * `vite/types/importMeta.d.ts:15` 的 `ImportMetaEnv` 帶 `[key: ImportMetaEnvFallbackKey]: any`，
 * interface 合併之後那個索引簽章還在，所以拼錯的 `VITE_*` 仍然是 `any`、`strict` 也擋不住。
 * 真要擋得另外宣告 `interface ViteTypeOptions { strictImportMetaEnv: unknown }`，
 * 那會讓所有未宣告的 `VITE_*` 變成編譯錯誤——目前刻意不開。
 */
interface ImportMetaEnv {
  /**
   * 靜態資產（`/pdf-assets/`、`/images/`）的來源。
   * 未設時走 `publicAsset()` 的原邏輯，由前端站台自己提供。
   * 設定後（例如 Cloudflare R2 的自訂網域）所有圖片改由該來源提供。
   */
  readonly VITE_ASSET_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/**
 * 節慶主題機制（2026-11 起）。
 *
 * - schedule.ts         純函式：台北日期、區間判斷（含跨年）、網址覆寫解析
 * - themes.ts           主題登錄表（id、起訖月日、html class、裝飾元件）與安靜路由
 * - SeasonalProvider    啟動時決定主題、在 <html> 掛 class、頁尾開關、答對慶祝特效層
 * - slots.tsx           頁面放裝飾的插槽；不該畫時回傳 null
 * - common.tsx          主題共用骨架：隱藏角色＋打氣泡泡、答對慶祝、及格橫幅＋散落、捲動飛過
 * - halloween/、christmas/  各主題的剪影、文案與組裝（配色在 index.css 的 .theme-<id>）
 *
 * 預覽：在 hash 前加 query，`/?seasonal=halloween#/`、`/?seasonal=christmas#/` 強制開、`/?seasonal=off#/` 強制關。
 */
export { default as SeasonalProvider } from './SeasonalProvider'
export { celebrateCorrectAnswer, useSeasonal } from './context'
export {
  SeasonalCompanion,
  SeasonalFooterToggle,
  SeasonalHeaderMark,
  SeasonalHeroDecor,
  SeasonalPassBanner,
  SeasonalScrollFlyer,
} from './slots'

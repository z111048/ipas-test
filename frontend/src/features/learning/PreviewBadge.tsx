import { Badge } from '../../components/ui'

/**
 * 預覽版內容的小標籤，放在 PageHeader 的 meta 列，不佔首屏整條。
 * 只在開發／預覽環境回傳元素；production 回傳 null（整段 tree-shake 掉，
 * tests/test_learning_frontend_static.py 會檢查 data-learning-preview 沒有進 bundle）。
 * 用函式而不是元件，讓呼叫端在 production 不會傳出一個空的 meta 列。
 */
export function previewBadge(availability?: 'preview' | 'published') {
  if (!import.meta.env.DEV || availability !== 'preview') return null
  return <span data-learning-preview><Badge tone="warning">搶先看・內容持續更新</Badge></span>
}

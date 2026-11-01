/**
 * 官方公告試題的 PDF 斷行殘留清理（只在顯示層做）。
 *
 * 公告試題由 PDF 抽取，原卷每行行尾的換行被轉成一個半形空白，於是題幹與選項裡
 * 出現「並 取代人工」「短時 間內」「少部分影 像」這類兩個中文字之間夾一個空白的情形
 * （16 份考卷約 2,440 處）。
 *
 * 為什麼不直接改 data/{level}/questions/*.json：參考詳解 pipeline 以題目內容做指紋
 * （scripts/run_codex_exam_reference_answers.py 的 question_content_fingerprint），
 * 改題目文字會讓 815 題的詳解全部對不上。所以原始 JSON 保持不動，進到畫面前才清理。
 *
 * 規則（刻意保守）：
 *  - 只移除「恰好一個」半形空白，且左右兩側都必須是 CJK 漢字（U+4E00–U+9FFF）、
 *    CJK 標點（U+3000–U+303F）或全形字元（U+FF00–U+FFEF）。
 *  - 旁邊是英文字母、數字或其他符號的空白一律保留（「GPS 經緯度」「2025年 9月」不動）。
 *  - 反引號包住的行內程式碼與 ``` 程式碼區塊不處理。
 *  - 冪等：清過的字串再清一次結果相同，所以載入時清過、元件再清一次也安全。
 */

const CJK = '\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef'
// 不用 lookbehind，避免舊版 Safari 不支援；以「左字元 + 空白 + 右側 lookahead」配對，
// 連續的「甲 乙 丙」會因為 lookahead 不吃掉右字元而逐一命中。
const WRAP_SPACE = new RegExp(`([${CJK}]) (?=[${CJK}])`, 'g')
const CODE_SPAN = /(```[\s\S]*?```|`[^`\n]*`)/

export function cleanExamText(text: string): string
export function cleanExamText(text: string | null | undefined): string | null | undefined
export function cleanExamText(text: string | null | undefined): string | null | undefined {
  if (!text || !text.includes(' ')) return text
  if (!text.includes('`')) return text.replace(WRAP_SPACE, '$1')
  // split 用的是有捕捉群組的正則：奇數索引是程式碼片段，原樣保留。
  return text
    .split(CODE_SPAN)
    .map((part, index) => (index % 2 === 1 ? part : part.replace(WRAP_SPACE, '$1')))
    .join('')
}

/** 題目物件的顯示用版本：只清題幹、題組情境與選項文字，其餘欄位（id、答案、圖片、
 *  context_blocks 程式碼）原樣保留。 */
export function cleanExamQuestion<
  T extends { question: string; context?: string; options: Record<string, string> },
>(question: T): T {
  const options = Object.fromEntries(
    Object.entries(question.options).map(([key, value]) => [key, cleanExamText(value)]),
  ) as T['options']
  return {
    ...question,
    question: cleanExamText(question.question),
    ...(question.context !== undefined ? { context: cleanExamText(question.context) } : {}),
    options,
  }
}

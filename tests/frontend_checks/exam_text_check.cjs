// 公告試題 PDF 斷行空白清理（frontend/src/utils/examText.ts）的單元檢查。
// 由 tests/test_layout_audit.py 在開瀏覽器前呼叫；也可單獨跑：node tests/frontend_checks/exam_text_check.cjs
//
// 與 concept_lookup_check.cjs 相同做法：用 frontend 自己的 typescript 把 .ts 轉譯成 CommonJS 再載入，
// 不依賴 Node 原生 TS 執行。
//
// 驗三件事：
//  1. 真實題目片段：該清的清掉，夾英數字的空白保留（含負例）。
//  2. 冪等、程式碼片段（反引號）不動。
//  3. resource catalog 的全部考卷（16 份，含兩份樣題）：清理後題幹／題組情境／選項
//     不再有「CJK 空白 CJK」，且被移除的只有這種空白（其他字元一個都沒變）。
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')

const ROOT = path.resolve(__dirname, '..', '..')
const ts = require(path.join(ROOT, 'frontend', 'node_modules', 'typescript'))
const source = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'utils', 'examText.ts'), 'utf8')
const { outputText, diagnostics } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  reportDiagnostics: true,
})
if (diagnostics && diagnostics.length > 0) {
  console.log('✗ examText.ts 轉譯失敗：' + diagnostics.map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('; '))
  process.exit(1)
}
const mod = new Module('examText.ts')
mod._compile(outputText, 'examText.ts')
const { cleanExamText, cleanExamQuestion } = mod.exports

const CJK = '\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef'
const LEFTOVER = new RegExp(`[${CJK}] [${CJK}]`)

const cases = [
  // 正例（真實題目片段：jr_1152_s1_q3、mid 樣題）
  ['並 取代人工', '並取代人工'],
  ['在高產量環境下短時 間內完成', '在高產量環境下短時間內完成'],
  ['僅有少部分影 像有專家標註', '僅有少部分影像有專家標註'],
  ['學習（Unsupervised Learning） 來處理？', '學習（Unsupervised Learning）來處理？'],
  ['連續 斷 行', '連續斷行'],
  ['全形標點，  兩個空白不動', '全形標點，  兩個空白不動'],
  // 負例：旁邊是英數字或其他符號的空白一律保留
  ['GPS 經緯度', 'GPS 經緯度'],
  ['Dify平台', 'Dify平台'],
  ['根據2025年 9月行政院', '根據2025年 9月行政院'],
  ['導入 AI系統', '導入 AI系統'],
  ['● 資料極度不平衡', '● 資料極度不平衡'],
  ['描述A：x_train, x_test 將影像', '描述A：x_train, x_test 將影像'],
  ['第一行\n第二行', '第一行\n第二行'],
  // 程式碼片段不動
  ['請看 `print("你好 世界")` 的 輸出', '請看 `print("你好 世界")` 的輸出'],
  ['```python\n# 中文 註解\n```\n之後 文字', '```python\n# 中文 註解\n```\n之後文字'],
  ['', ''],
]

let failed = 0
for (const [input, expected] of cases) {
  const actual = cleanExamText(input)
  const again = cleanExamText(actual)
  const ok = actual === expected && again === actual
  if (!ok) failed += 1
  console.log(`  ${ok ? '✓' : '✗'} ${JSON.stringify(input)} → ${JSON.stringify(actual)}${ok ? '' : `（預期 ${JSON.stringify(expected)}${again !== actual ? '；不冪等' : ''}）`}`)
}
for (const value of [undefined, null]) {
  const ok = cleanExamText(value) === value
  if (!ok) failed += 1
  console.log(`  ${ok ? '✓' : '✗'} ${value} 原樣回傳`)
}

// ---- 全部考卷（以 resource catalog 為準，含兩份樣題 sample_exam.json）
const catalog = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'resource_catalog.json'), 'utf8'))
const LEVEL_DIR = { junior: '初級', middle: '中級' }
const files = catalog.exams.map((exam) => path.join(ROOT, 'data', LEVEL_DIR[exam.levelId], 'questions', exam.questionFile))
let removed = 0
let questions = 0
const leftovers = []
const corrupted = []
for (const file of files) {
  const exam = JSON.parse(fs.readFileSync(file, 'utf8'))
  for (const raw of exam.questions) {
    questions += 1
    const cleaned = cleanExamQuestion(raw)
    if (cleaned.id !== raw.id || cleaned.answer !== raw.answer || cleaned.context_blocks !== raw.context_blocks) {
      corrupted.push(`${raw.id}：非文字欄位被改動`)
    }
    const pairs = [['question', raw.question, cleaned.question], ['context', raw.context, cleaned.context]]
    for (const key of Object.keys(raw.options)) pairs.push([`option ${key}`, raw.options[key], cleaned.options[key]])
    for (const [field, before, after] of pairs) {
      if (before === undefined) continue
      if (LEFTOVER.test(after)) leftovers.push(`${raw.id} ${field}：${after.match(new RegExp(`.{0,6}[${CJK}] [${CJK}].{0,6}`))[0]}`)
      // 被移除的只能是空白：把兩邊的空白都拿掉後必須完全相同
      if (before.replace(/ /g, '') !== after.replace(/ /g, '')) corrupted.push(`${raw.id} ${field}：非空白字元被改動`)
      removed += before.length - after.length
    }
  }
}
const dataOk = files.length >= 16 && leftovers.length === 0 && corrupted.length === 0 && removed > 2000
if (!dataOk) failed += 1
console.log(`  ${dataOk ? '✓' : '✗'} ${files.length} 份考卷 ${questions} 題：清掉 ${removed} 個斷行空白，殘留 ${leftovers.length}、誤改 ${corrupted.length}`)
for (const line of [...leftovers, ...corrupted].slice(0, 8)) console.log(`      ${line}`)

if (failed > 0) {
  console.log(`✗ examText 檢查 ${failed} 項失敗`)
  process.exit(1)
}
console.log('✓ examText 檢查全部通過')

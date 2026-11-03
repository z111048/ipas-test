// 節慶主題排程的純函式檢查。由 tests/test_seasonal_theme.py 呼叫（run_all 第 1 項 test_resource_catalog 會帶到）。
//
// 用 frontend 自己的 typescript 把 frontend/src/features/seasonal/schedule.ts 轉譯後載入
// （同 concept_lookup_check.cjs 的做法，不依賴 Node 的原生 TS 執行）。
// 驗：台北時間換日、含首尾的區間、跨年區間、網址覆寫解析與主題決策。
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')

const ROOT = path.resolve(__dirname, '..', '..')
const ts = require(path.join(ROOT, 'frontend', 'node_modules', 'typescript'))
const file = path.join(ROOT, 'frontend', 'src', 'features', 'seasonal', 'schedule.ts')
const { outputText, diagnostics } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  reportDiagnostics: true,
})
if (diagnostics && diagnostics.length > 0) {
  console.log('✗ schedule.ts 轉譯失敗：' + diagnostics.map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('; '))
  process.exit(1)
}
const mod = new Module('schedule.ts')
mod._compile(outputText, 'schedule.ts')
const { taipeiMonthDay, isWithinWindow, parseSeasonalOverride, resolveSeasonalTheme } = mod.exports

// 與 frontend/src/features/seasonal/themes.ts 的萬聖節區間一致（下面另以原始碼比對防漂移）。
const halloween = { id: 'halloween', start: { month: 10, day: 15 }, end: { month: 11, day: 7 } }
const winter = { id: 'winter', start: { month: 12, day: 20 }, end: { month: 1, day: 5 } }
const themes = [halloween, winter]
const md = (month, day) => ({ month, day })

let failed = 0
function check(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  if (!ok) failed += 1
  console.log(`  ${ok ? '✓' : '✗'} ${label}${ok ? '' : `：得到 ${JSON.stringify(actual)}，預期 ${JSON.stringify(expected)}`}`)
}

// 台北時間（UTC+8）換日
check('UTC 10/14 15:59 = 台北 10/14 23:59', taipeiMonthDay(new Date('2026-10-14T15:59:59Z')), md(10, 14))
check('UTC 10/14 16:00 = 台北 10/15 00:00', taipeiMonthDay(new Date('2026-10-14T16:00:00Z')), md(10, 15))
check('UTC 11/07 15:59 = 台北 11/07 23:59', taipeiMonthDay(new Date('2026-11-07T15:59:59Z')), md(11, 7))
check('UTC 11/07 16:00 = 台北 11/08', taipeiMonthDay(new Date('2026-11-07T16:00:00Z')), md(11, 8))
check('UTC 12/31 16:00 = 台北隔年 1/1', taipeiMonthDay(new Date('2026-12-31T16:00:00Z')), md(1, 1))
check('閏年 2/29', taipeiMonthDay(new Date('2028-02-28T16:30:00Z')), md(2, 29))

// 一般區間，含首尾
check('10/14 不在萬聖節', isWithinWindow(md(10, 14), halloween), false)
check('10/15 起日在內', isWithinWindow(md(10, 15), halloween), true)
check('10/31 在內', isWithinWindow(md(10, 31), halloween), true)
check('11/3 在內', isWithinWindow(md(11, 3), halloween), true)
check('11/7 迄日在內', isWithinWindow(md(11, 7), halloween), true)
check('11/8 不在', isWithinWindow(md(11, 8), halloween), false)
check('1/1 不在', isWithinWindow(md(1, 1), halloween), false)
check('同月不同日：10/9 不在、11/1 在', [isWithinWindow(md(10, 9), halloween), isWithinWindow(md(11, 1), halloween)], [false, true])

// 跨年區間
check('跨年：12/19 不在', isWithinWindow(md(12, 19), winter), false)
check('跨年：12/20 起日在內', isWithinWindow(md(12, 20), winter), true)
check('跨年：12/31 在內', isWithinWindow(md(12, 31), winter), true)
check('跨年：1/1 在內', isWithinWindow(md(1, 1), winter), true)
check('跨年：1/5 迄日在內', isWithinWindow(md(1, 5), winter), true)
check('跨年：1/6 不在', isWithinWindow(md(1, 6), winter), false)
check('跨年：7/1 不在', isWithinWindow(md(7, 1), winter), false)
check('單日區間', isWithinWindow(md(4, 1), { start: md(4, 1), end: md(4, 1) }), true)

// 網址覆寫
const ids = themes.map((t) => t.id)
check('沒帶 query', parseSeasonalOverride('', ids), null)
check('?seasonal=off', parseSeasonalOverride('?seasonal=off', ids), { kind: 'off' })
check('?seasonal=OFF（不分大小寫）', parseSeasonalOverride('?seasonal=OFF', ids), { kind: 'off' })
check('?seasonal=halloween', parseSeasonalOverride('?foo=1&seasonal=halloween', ids), { kind: 'force', id: 'halloween' })
check('不認得的主題 → 照日期', parseSeasonalOverride('?seasonal=easter', ids), null)
check('空值 → 照日期', parseSeasonalOverride('?seasonal=', ids), null)

// 主題決策（覆寫 > 日期）
const id = (theme) => (theme ? theme.id : null)
const at = (iso) => new Date(iso)
check('今天 2026-11-03 → 萬聖節', id(resolveSeasonalTheme(themes, at('2026-11-03T04:00:00Z'), null)), 'halloween')
check('台北 10/15 00:00 → 萬聖節', id(resolveSeasonalTheme(themes, at('2026-10-14T16:00:00Z'), null)), 'halloween')
check('台北 11/08 00:00 → 無', id(resolveSeasonalTheme(themes, at('2026-11-07T16:00:00Z'), null)), null)
check('明年同一天仍生效（每年重複）', id(resolveSeasonalTheme(themes, at('2027-10-20T04:00:00Z'), null)), 'halloween')
check('跨年主題 1/2', id(resolveSeasonalTheme(themes, at('2027-01-02T04:00:00Z'), null)), 'winter')
check('6 月 → 無', id(resolveSeasonalTheme(themes, at('2026-06-01T04:00:00Z'), null)), null)
check('期間內 ?seasonal=off → 無', id(resolveSeasonalTheme(themes, at('2026-11-03T04:00:00Z'), { kind: 'off' })), null)
check('期間外 ?seasonal=halloween → 萬聖節', id(resolveSeasonalTheme(themes, at('2026-06-01T04:00:00Z'), { kind: 'force', id: 'halloween' })), 'halloween')
check('期間內強制另一個主題', id(resolveSeasonalTheme(themes, at('2026-11-03T04:00:00Z'), { kind: 'force', id: 'winter' })), 'winter')

// 防漂移：themes.ts 的萬聖節區間要和這裡一致（10/15–11/7）。
const themesSource = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'features', 'seasonal', 'themes.ts'), 'utf8')
const declared = /id:\s*'halloween'[\s\S]*?start:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}[\s\S]*?end:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}/.exec(themesSource)
check('themes.ts 萬聖節區間 = 10/15–11/7', declared ? declared.slice(1).map(Number) : null, [10, 15, 11, 7])

if (failed > 0) {
  console.log(`✗ 節慶排程檢查 ${failed} 項失敗`)
  process.exit(1)
}
console.log('✓ 節慶排程：台北換日、含首尾、跨年、網址覆寫皆正確')

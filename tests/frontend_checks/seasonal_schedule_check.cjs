// 節慶主題排程的純函式檢查。由 tests/test_seasonal_theme.py 呼叫（run_all 第 1 項 test_resource_catalog 會帶到）。
//
// 用 frontend 自己的 typescript 把 frontend/src/features/seasonal/schedule.ts 轉譯後載入
// （同 concept_lookup_check.cjs 的做法，不依賴 Node 的原生 TS 執行）。
// 驗：台北時間換日、含首尾的區間、跨年區間、網址覆寫解析與主題決策（萬聖節、聖誕節），
// 以及重疊規則（同一天多個主題符合時，登錄表中排前面的優先）。
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

// 與 frontend/src/features/seasonal/themes.ts 的萬聖節、聖誕節區間一致（下面另以原始碼比對防漂移）。
const halloween = { id: 'halloween', start: { month: 10, day: 15 }, end: { month: 11, day: 7 } }
const christmas = { id: 'christmas', start: { month: 12, day: 1 }, end: { month: 12, day: 26 } }
const winter = { id: 'winter', start: { month: 12, day: 20 }, end: { month: 1, day: 5 } }
const registry = [halloween, christmas]
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

// 聖誕節區間（12/1–12/26，含首尾）
check('聖誕：11/30 不在', isWithinWindow(md(11, 30), christmas), false)
check('聖誕：12/1 起日在內', isWithinWindow(md(12, 1), christmas), true)
check('聖誕：12/25 在內', isWithinWindow(md(12, 25), christmas), true)
check('聖誕：12/26 迄日在內', isWithinWindow(md(12, 26), christmas), true)
check('聖誕：12/27 不在', isWithinWindow(md(12, 27), christmas), false)
check('UTC 11/30 15:59 = 台北 11/30 23:59', taipeiMonthDay(new Date('2026-11-30T15:59:59Z')), md(11, 30))
check('UTC 11/30 16:00 = 台北 12/1', taipeiMonthDay(new Date('2026-11-30T16:00:00Z')), md(12, 1))
check('UTC 12/26 16:00 = 台北 12/27', taipeiMonthDay(new Date('2026-12-26T16:00:00Z')), md(12, 27))

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

// 實際登錄表（萬聖節＋聖誕節）的決策
const regIds = registry.map((t) => t.id)
check('?seasonal=christmas 解析', parseSeasonalOverride('?seasonal=christmas', regIds), { kind: 'force', id: 'christmas' })
check('?seasonal=Christmas（不分大小寫）', parseSeasonalOverride('?seasonal=Christmas', regIds), { kind: 'force', id: 'christmas' })
check('今天 2026-11-07（萬聖節最後一天）→ 萬聖節', id(resolveSeasonalTheme(registry, at('2026-11-07T04:00:00Z'), null)), 'halloween')
check('台北 11/08 00:00 → 無', id(resolveSeasonalTheme(registry, at('2026-11-07T16:00:00Z'), null)), null)
check('台北 11/30 23:59 → 無', id(resolveSeasonalTheme(registry, at('2026-11-30T15:59:59Z'), null)), null)
check('台北 12/1 00:00 → 聖誕節', id(resolveSeasonalTheme(registry, at('2026-11-30T16:00:00Z'), null)), 'christmas')
check('12/25 → 聖誕節', id(resolveSeasonalTheme(registry, at('2026-12-25T04:00:00Z'), null)), 'christmas')
check('台北 12/26 23:59 → 聖誕節', id(resolveSeasonalTheme(registry, at('2026-12-26T15:59:59Z'), null)), 'christmas')
check('台北 12/27 00:00 → 無', id(resolveSeasonalTheme(registry, at('2026-12-26T16:00:00Z'), null)), null)
check('明年 12/10 仍是聖誕節（每年重複）', id(resolveSeasonalTheme(registry, at('2027-12-10T04:00:00Z'), null)), 'christmas')
check('萬聖節期間 ?seasonal=christmas → 聖誕節', id(resolveSeasonalTheme(registry, at('2026-11-07T04:00:00Z'), { kind: 'force', id: 'christmas' })), 'christmas')
check('聖誕節期間 ?seasonal=halloween → 萬聖節', id(resolveSeasonalTheme(registry, at('2026-12-20T04:00:00Z'), { kind: 'force', id: 'halloween' })), 'halloween')
check('聖誕節期間 ?seasonal=off → 無', id(resolveSeasonalTheme(registry, at('2026-12-20T04:00:00Z'), { kind: 'off' })), null)

// 重疊規則：同一天多個主題符合時，登錄表中排前面的優先
const overlapA = { id: 'a', start: md(12, 1), end: md(12, 26) }
const overlapB = { id: 'b', start: md(12, 20), end: md(1, 5) }
check('重疊日 12/24：[a, b] → a', id(resolveSeasonalTheme([overlapA, overlapB], at('2026-12-24T04:00:00Z'), null)), 'a')
check('重疊日 12/24：[b, a] → b', id(resolveSeasonalTheme([overlapB, overlapA], at('2026-12-24T04:00:00Z'), null)), 'b')
check('非重疊日 12/28 → 只有 b 符合', id(resolveSeasonalTheme([overlapA, overlapB], at('2026-12-28T04:00:00Z'), null)), 'b')

// 防漂移：themes.ts 的萬聖節區間要和這裡一致（10/15–11/7）。
const themesSource = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'features', 'seasonal', 'themes.ts'), 'utf8')
const declared = /id:\s*'halloween'[\s\S]*?start:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}[\s\S]*?end:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}/.exec(themesSource)
check('themes.ts 萬聖節區間 = 10/15–11/7', declared ? declared.slice(1).map(Number) : null, [10, 15, 11, 7])
const declaredXmas = /id:\s*'christmas'[\s\S]*?start:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}[\s\S]*?end:\s*\{\s*month:\s*(\d+),\s*day:\s*(\d+)\s*\}/.exec(themesSource)
check('themes.ts 聖誕節區間 = 12/1–12/26', declaredXmas ? declaredXmas.slice(1).map(Number) : null, [12, 1, 12, 26])
check('themes.ts 登錄順序：萬聖節在聖誕節前', themesSource.indexOf("id: 'halloween'") < themesSource.indexOf("id: 'christmas'"), true)

// 實際登錄的兩個主題一整年都不重疊（重疊時雖有「排前面優先」的規則，但目前不該依賴它）。
let overlapDays = []
for (let m = 1; m <= 12; m += 1) {
  for (let d = 1; d <= 31; d += 1) {
    if (registry.filter((t) => isWithinWindow(md(m, d), t)).length > 1) overlapDays.push(`${m}/${d}`)
  }
}
check('萬聖節與聖誕節區間不重疊', overlapDays, [])

if (failed > 0) {
  console.log(`✗ 節慶排程檢查 ${failed} 項失敗`)
  process.exit(1)
}
console.log('✓ 節慶排程：台北換日、含首尾、跨年、網址覆寫皆正確')

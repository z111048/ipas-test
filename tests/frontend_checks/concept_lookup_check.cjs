// /concepts?c= 解析順序檢查（LP-210C）。由 tests/test_learning_frontend_static.py 呼叫。
//
// 用 frontend 自己的 typescript 套件把 frontend/src/data/conceptLookup.ts 轉譯後載入，
// 不依賴 Node 22 的原生 TS 執行——CI（deploy.yml）用的是 Node 20。
// 驗三段順序 id → 目前正式名稱 → previousNames，尤其是「兩個概念互換名字」：
// 真實資料的 previousNames 目前全空，只有這裡走得到第三段。
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')

const ROOT = path.resolve(__dirname, '..', '..')
const ts = require(path.join(ROOT, 'frontend', 'node_modules', 'typescript'))
const source = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'data', 'conceptLookup.ts'), 'utf8')
const { outputText, diagnostics } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  reportDiagnostics: true,
})
if (diagnostics && diagnostics.length > 0) {
  console.log('✗ conceptLookup.ts 轉譯失敗：' + diagnostics.map((d) => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('; '))
  process.exit(1)
}
const lookup = new Module('conceptLookup.ts')
lookup._compile(outputText, 'conceptLookup.ts')
const { resolveConcept, resolveByLegacyName } = lookup.exports

// 甲／丙互換過名字：A 現在叫「甲」（以前叫「丙」），B 現在叫「丙」（以前叫「甲」）。
const swapped = [
  { id: 'topic-aaaaaaaa', name: '甲', previousNames: ['丙'], parent: 'p' },
  { id: 'topic-bbbbbbbb', name: '丙', previousNames: ['甲'], parent: 'p' },
  { id: 'topic-cccccccc', name: '乙', previousNames: ['舊乙', '更舊的乙'], parent: 'p' },
]

const cases = [
  ['id 直接命中', 'topic-cccccccc', 'topic-cccccccc'],
  ['目前正式名稱', '乙', 'topic-cccccccc'],
  ['previousNames 第一個', '舊乙', 'topic-cccccccc'],
  ['previousNames 第二個', '更舊的乙', 'topic-cccccccc'],
  ['互換名字：正式名稱「丙」必須贏過 A 的 previousNames', '丙', 'topic-bbbbbbbb'],
  ['互換名字：正式名稱「甲」必須贏過 B 的 previousNames', '甲', 'topic-aaaaaaaa'],
  ['空值', '', null],
  ['對不到', 'topic-not-a-real-topic', null],
  ['對不到（名稱）', '不存在的概念', null],
]

let failed = 0
for (const [label, requested, expected] of cases) {
  const actual = resolveConcept(swapped, requested)?.id ?? null
  const ok = actual === expected
  if (!ok) failed += 1
  console.log(`  ${ok ? '✓' : '✗'} ${label}：?c=${requested || '（空）'} → ${actual ?? 'null'}${ok ? '' : `（預期 ${expected ?? 'null'}）`}`)
}

// 順序若被合成一次 find（name === v || previousNames.includes(v)），下面這條就會解析到 A
if (resolveByLegacyName(swapped, '丙')?.id !== 'topic-bbbbbbbb') {
  failed += 1
  console.log('  ✗ resolveByLegacyName 沒有讓目前正式名稱優先於他人的 previousNames')
}
// id 命中時不得再落到名稱：即使某概念的 previousNames 剛好含一個 id 字串
const idLikeName = [
  { id: 'topic-11111111', name: '一', previousNames: ['topic-22222222'], parent: 'p' },
  { id: 'topic-22222222', name: '二', previousNames: [], parent: 'p' },
]
if (resolveConcept(idLikeName, 'topic-22222222')?.id !== 'topic-22222222') {
  failed += 1
  console.log('  ✗ id 命中沒有優先於 previousNames')
}

if (failed > 0) {
  console.log(`✗ conceptLookup：${failed} 條不符`)
  process.exit(1)
}
console.log(`✓ conceptLookup：${cases.length + 2} 條解析順序全部正確`)

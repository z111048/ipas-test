#!/usr/bin/env node
/**
 * LaTeX → MathML（給 export_guide_epub.py 用）。
 *
 * EPUB 3 原生支援 MathML，閱讀器會排版；直接塞 LaTeX 原始碼的話，
 * 讀者看到的是「$$ P(a\leq X\leq b)=\int_{a}^{b}f(x)dx $$」這串字。
 *
 * stdin：[{ "latex": "...", "display": true }, ...]
 * stdout：["<math …>…</math>" 或 null, ...]（null = 這條轉不出來，呼叫端退回原文）
 */
const path = require('node:path');
const repo = path.resolve(__dirname, '..');
const katex = require(path.join(repo, 'frontend', 'node_modules', 'katex'));

let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  let items;
  try {
    items = JSON.parse(raw);
  } catch (error) {
    process.stderr.write(`bad input JSON: ${error.message}\n`);
    process.exit(1);
  }
  const out = items.map(({ latex, display }) => {
    try {
      const html = katex.renderToString(String(latex), {
        output: 'mathml',
        displayMode: Boolean(display),
        throwOnError: true,     // 轉不出來就退回原文，不要輸出紅色錯誤訊息給讀者
        strict: false,
      });
      // renderToString 會包一層 <span class="katex">，EPUB 只要裡面的 <math>
      const match = html.match(/<math[\s\S]*<\/math>/);
      if (!match) return null;
      // KaTeX 把 \min / \max 渲染成 <mi>min</mi><mo>&#x2061;</mo>（不可見的「函數套用」
      // 運算子）。放在 <msub> 裡就變成三個子元素，但 msub 規定只能兩個 —— EPUBCheck
      // 會報 RSC-005「element "mo" not allowed here」。這個運算子純屬語意、不顯示，拿掉即可。
      return match[0].replace(/<mo>\u2061<\/mo>/g, '');
    } catch {
      return null;
    }
  });
  process.stdout.write(JSON.stringify(out));
});

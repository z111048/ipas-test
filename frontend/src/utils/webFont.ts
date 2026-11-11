// 網路字型延後啟用。
// index.html 的字型樣式表以 media="print" 低優先權載入，不會啟用字型。
// 第一次造訪時，字型檔（約 700 KB）若在首屏就開始下載，會和路由頁的程式搶頻寬，
// 所以等路由頁真的渲染出來（App.tsx 的 WebFontGate）才呼叫這裡切成 media="all"。
// 回訪者的旗標 ipas:webfont 已存在，由 index.html 內嵌小段程式在樣式表載完時直接啟用，不必等到這裡。
// 可重複呼叫；找不到元素或 localStorage 不可用時不會出錯。

export function activateWebFont(): void {
  const link = document.getElementById('webfont') as HTMLLinkElement | null
  if (link && link.media !== 'all') link.media = 'all'
  try {
    localStorage.setItem('ipas:webfont', '1')
  } catch {
    // 無痕模式等情況 localStorage 不可用，忽略
  }
}

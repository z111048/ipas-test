// @types/react-syntax-highlighter 沒有涵蓋 dist/esm 的子路徑，這裡補上實際用到的三個。
declare module 'react-syntax-highlighter/dist/esm/prism-light' {
  import type { PrismLight } from 'react-syntax-highlighter'
  export default PrismLight
}
declare module 'react-syntax-highlighter/dist/esm/languages/prism/python' {
  const language: unknown
  export default language
}
declare module 'react-syntax-highlighter/dist/esm/styles/prism/one-light' {
  const style: { [key: string]: React.CSSProperties }
  export default style
}

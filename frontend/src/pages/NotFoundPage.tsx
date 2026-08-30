import { Link } from 'react-router-dom'
import { StatePanel } from '../components/ui'

export default function NotFoundPage() {
  return (
    <div className="page-shell">
      <StatePanel
        tone="error"
        title="找不到頁面"
        action={<Link to="/" className="btn-primary min-h-11">回到首頁</Link>}
      >
        這個網址不存在，或內容已經移動。
      </StatePanel>
    </div>
  )
}

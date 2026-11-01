import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui'
import { navLabel } from '../constants/navLabels'

export default function NotFoundPage() {
  return (
    <div className="page-shell">
      <PageHeader
        variant="plain"
        title={navLabel('notFound')}
        description="這個網址不存在，或內容已經移動。"
        actions={<Link to="/" className="btn-primary">回到首頁</Link>}
      />
    </div>
  )
}

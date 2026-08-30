import { Component, type ErrorInfo, type ReactNode } from 'react'
import StatePanel from '../ui/StatePanel'

interface Props {
  children: ReactNode
  resetKey: string
}

interface State {
  error: Error | null
}

export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: unknown): State {
    return { error: error instanceof Error ? error : new Error(String(error)) }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[AppErrorBoundary]', error, info.componentStack)
  }

  componentDidUpdate(previous: Props) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null })
    }
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="page-shell">
        <StatePanel
          tone="error"
          title="頁面暫時無法顯示"
          action={(
            <button type="button" className="btn-primary min-h-11" onClick={() => window.location.reload()}>
              重新載入
            </button>
          )}
        >
          請重新載入頁面；若問題持續發生，可先回到其他章節。
        </StatePanel>
      </div>
    )
  }
}

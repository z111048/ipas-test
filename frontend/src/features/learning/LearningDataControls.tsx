import { useRef, useState, type ChangeEvent } from 'react'
import { StatePanel } from '../../components/ui'
import { learnerRepository, type ImportPreview } from './state/repository'

export default function LearningDataControls() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<ImportPreview>()
  const [message, setMessage] = useState<string>()
  const [error, setError] = useState<string>()

  const exportData = async () => {
    try {
      const raw = await learnerRepository.exportData()
      const url = URL.createObjectURL(new Blob([raw], { type: 'application/json' }))
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `ipas-learning-backup-${new Date().toISOString().slice(0, 10)}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      setMessage('備份已下載。')
      setError(undefined)
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  const selectFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      const next = await learnerRepository.previewImport(await file.text())
      setPreview(next)
      setMessage(undefined)
      setError(undefined)
    } catch (reason) {
      setPreview(undefined)
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  const importData = async () => {
    if (!preview) return
    try {
      await learnerRepository.importData(preview.raw)
      setMessage(`匯入完成：檢查 ${preview.attempts} 筆作答、${preview.progress} 筆進度；衝突作答另存為歷史紀錄。`)
      setPreview(undefined)
      setError(undefined)
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  const clearData = async () => {
    if (!window.confirm('確定清除這個瀏覽器的學習作答與進度？建議先匯出備份。')) return
    try {
      await learnerRepository.clearData()
      setMessage('這個瀏覽器的學習紀錄已清除。')
      setPreview(undefined)
      setError(undefined)
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  return <section className="surface mt-5 p-5" aria-label="學習紀錄備份">
    <h2 className="section-title mb-2">本機學習紀錄</h2>
    <p className="text-sm leading-6 text-text-light">紀錄只存在這個瀏覽器。匯入會先驗證版本、欄位與完整快照 hash；備份內的分數不會被當成可信成績。</p>
    {error && <StatePanel tone="error" title="學習紀錄操作失敗" className="mt-3">{error}</StatePanel>}
    {message && <StatePanel title="學習紀錄" className="mt-3">{message}</StatePanel>}
    {preview && <StatePanel title="確認匯入" className="mt-3">檔案含 {preview.attempts} 筆作答、{preview.progress} 筆進度。進行中作答會降為歷史紀錄，同 ID 內容不同時另存且不覆寫。<div className="mt-3"><button className="btn-primary" onClick={() => void importData()}>確認匯入</button></div></StatePanel>}
    <div className="mt-4 flex flex-wrap gap-3">
      <button className="btn-secondary" onClick={() => void exportData()}>匯出 JSON 備份</button>
      <button className="btn-secondary" onClick={() => inputRef.current?.click()}>選擇 JSON 匯入</button>
      <button className="btn-secondary" onClick={() => void clearData()}>清除本機紀錄</button>
      <input ref={inputRef} className="sr-only" type="file" accept="application/json,.json" onChange={selectFile} />
    </div>
  </section>
}

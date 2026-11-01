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
      setMessage('備份檔已下載，請妥善保存；之後可用「還原紀錄」放回。')
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
      setMessage(`還原完成：檢查 ${preview.attempts} 筆作答、${preview.progress} 筆進度；與現有紀錄衝突的作答另存為歷史紀錄。`)
      setPreview(undefined)
      setError(undefined)
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  const clearData = async () => {
    if (!window.confirm('確定清除這個瀏覽器的學習作答與進度？建議先按「備份我的紀錄」。')) return
    try {
      await learnerRepository.clearData()
      setMessage('這個瀏覽器的學習紀錄已清除。')
      setPreview(undefined)
      setError(undefined)
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  // 收成 <details>，不和課程內容搶版面；需要時再展開。
  return <details className="surface group mt-5" aria-label="學習紀錄備份">
    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-[inherit] px-5 py-3 text-ui font-semibold text-primary [&::-webkit-details-marker]:hidden">
      <span>我的學習紀錄（備份／還原）</span>
      <span aria-hidden="true" className="text-text-light transition-transform group-open:rotate-180">▾</span>
    </summary>
    <div className="border-t border-border px-5 pb-5 pt-4">
      <p className="text-body leading-7 text-text-light">作答與進度只存在這個瀏覽器。換電腦或清除瀏覽器資料前，先備份；還原前會先檢查備份檔是否完整、未被修改，還原後的分數僅供個人參考。</p>
      {error && <StatePanel tone="error" title="學習紀錄操作失敗" className="mt-3">{error}</StatePanel>}
      {message && <StatePanel title="學習紀錄" className="mt-3">{message}</StatePanel>}
      {preview && <StatePanel title="確認還原" className="mt-3">備份檔含 {preview.attempts} 筆作答、{preview.progress} 筆進度。進行中的作答會改列為歷史紀錄；與現有紀錄衝突時會另存一份，不會覆蓋。<div className="mt-3"><button type="button" className="btn-primary" onClick={() => void importData()}>確認還原</button></div></StatePanel>}
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button type="button" className="btn-secondary" onClick={() => void exportData()}>備份我的紀錄</button>
        <button type="button" className="btn-secondary" onClick={() => inputRef.current?.click()}>還原紀錄</button>
        <button type="button" className="btn-secondary" onClick={() => void clearData()}>清除紀錄</button>
        <input ref={inputRef} className="sr-only" type="file" accept="application/json,.json" aria-label="選擇備份檔" onChange={selectFile} />
      </div>
      <p className="mt-2 text-meta text-text-light">「備份我的紀錄」會下載一個備份檔（.json）；「還原紀錄」時選擇同一個檔案即可。</p>
    </div>
  </details>
}

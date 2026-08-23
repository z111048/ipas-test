import { useMemo, useState } from 'react'
import primaryRaw from '../generated/primaryGlossary.json'
import middleRaw from '../generated/middleGlossary.json'
import { FilterBar, PageHeader, SegmentedControl, StatePanel } from '../components/ui'

interface GlossaryTerm {
  zh: string
  en: string
  definition: string
  example: string
}

interface GlossaryData {
  level: string
  subjects: Record<string, {
    subject: string
    terms: GlossaryTerm[]
  }>
}

const bundles: Record<string, GlossaryData> = {
  初級: primaryRaw as GlossaryData,
  中級: middleRaw as GlossaryData,
}
const levels = Object.keys(bundles)

export default function GlossaryPage() {
  const [level, setLevel] = useState(levels[0])
  const [subjectId, setSubjectId] = useState(Object.keys(bundles[levels[0]].subjects)[0])
  const [query, setQuery] = useState('')

  const glossary = bundles[level]
  const subjectIds = Object.keys(glossary.subjects)
  // switching level leaves the old subject id selected for one render; fall back
  // to the first subject of the level actually being shown
  const activeSubjectId = subjectIds.includes(subjectId) ? subjectId : subjectIds[0]
  const subject = glossary.subjects[activeSubjectId]

  const terms = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return subject.terms
    return subject.terms.filter((term) =>
      [term.zh, term.en, term.definition, term.example]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    )
  }, [query, subject])

  const totalTerms = subjectIds.reduce((sum, id) => sum + glossary.subjects[id].terms.length, 0)

  return (
    <div className="page-shell">
      <PageHeader
        className="mb-5"
        eyebrow="名詞解釋"
        title="關鍵字整理"
        description="依歷屆試題出現頻率整理的中英文名詞、定義與應用案例，初級與中級各自分科呈現。"
        meta={
          <>
            <span className="pill">{level}</span>
            <span className="pill pill-muted">{totalTerms} 個關鍵字</span>
          </>
        }
      />

      <FilterBar
        className="mb-4"
        title="篩選關鍵字"
        result={`符合篩選 ${terms.length} 個`}
        action={(query || level !== levels[0] || activeSubjectId !== Object.keys(bundles[levels[0]].subjects)[0]) && (
          <button
            type="button"
            onClick={() => {
              setLevel(levels[0])
              setSubjectId(Object.keys(bundles[levels[0]].subjects)[0])
              setQuery('')
            }}
            className="btn-outline min-h-11"
          >
            清除篩選
          </button>
        )}
      >
        <SegmentedControl
          label="級別"
          value={level}
          options={levels.map((name) => ({ value: name, label: name }))}
          onChange={(name) => {
            setLevel(name)
            setSubjectId(Object.keys(bundles[name].subjects)[0])
          }}
        />
        <SegmentedControl
          label="科目"
          value={activeSubjectId}
          className="xl:col-span-2"
          options={subjectIds.map((id) => ({
            value: id,
            label: glossary.subjects[id].subject.replace(/^中級/, ''),
          }))}
          onChange={setSubjectId}
        />
        <label className="text-[0.82rem] text-text-light">
          關鍵字
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋中文、英文、定義或案例"
            className="mt-1 min-h-11 w-full rounded-lg border border-border bg-white px-3 py-2 text-[0.88rem] text-app-text outline-none focus:border-accent"
          />
        </label>
      </FilterBar>

      <div className="bg-card rounded-xl shadow-sm border border-border overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <div className="text-primary font-semibold">{level}　{subject.subject}</div>
          <div className="text-[0.8rem] text-text-light mt-1">
            本科共 {subject.terms.length} 個關鍵字（{level}合計 {totalTerms} 個），符合篩選 {terms.length} 個
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse text-[0.88rem]">
            <thead>
              <tr className="bg-[#f5f7fa] text-primary">
                <th className="w-[16%] p-3 text-left border-b border-border">中文</th>
                <th className="w-[22%] p-3 text-left border-b border-border">英文</th>
                <th className="w-[31%] p-3 text-left border-b border-border">定義</th>
                <th className="w-[31%] p-3 text-left border-b border-border">案例說明</th>
              </tr>
            </thead>
            <tbody>
              {terms.map((term) => (
                <tr key={`${term.zh}-${term.en}`} className="align-top hover:bg-[#f7fbff]">
                  <td className="p-3 border-b border-border font-semibold text-primary">{term.zh}</td>
                  <td className="p-3 border-b border-border text-accent">{term.en}</td>
                  <td className="p-3 border-b border-border leading-7 content-justify">{term.definition}</td>
                  <td className="p-3 border-b border-border leading-7 content-justify">{term.example}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {terms.length === 0 && (
          <div className="p-5">
            <StatePanel
              tone="empty"
              title="找不到符合條件的關鍵字"
              action={(
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="btn-outline min-h-11"
                >
                  清除搜尋字
                </button>
              )}
            >
              請改用其他中文、英文、定義或案例關鍵字。
            </StatePanel>
          </div>
        )}
      </div>
    </div>
  )
}

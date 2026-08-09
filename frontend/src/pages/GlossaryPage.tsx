import { useMemo, useState } from 'react'
import primaryRaw from '../generated/primaryGlossary.json'
import middleRaw from '../generated/middleGlossary.json'

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
    <div>
      <div className="text-[0.78rem] font-semibold text-accent mb-1">名詞解釋</div>
      <div className="text-2xl font-bold text-primary mb-1">關鍵字整理</div>
      <div className="text-text-light mb-5">
        依歷屆試題出現頻率整理的中英文名詞、定義與應用案例，初級與中級各自分科呈現。
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          <div className="flex flex-wrap gap-2">
            {levels.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => {
                  setLevel(name)
                  setSubjectId(Object.keys(bundles[name].subjects)[0])
                }}
                className={`px-3 py-2 rounded-lg border text-[0.85rem] cursor-pointer ${
                  level === name
                    ? 'border-accent bg-accent text-white'
                    : 'border-border bg-white text-primary hover:border-accent'
                }`}
              >
                {name}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2 lg:border-l lg:border-border lg:pl-3">
            {subjectIds.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => setSubjectId(id)}
                className={`px-3 py-2 rounded-lg border text-[0.85rem] cursor-pointer ${
                  activeSubjectId === id
                    ? 'border-accent bg-accent text-white'
                    : 'border-border bg-white text-primary hover:border-accent'
                }`}
              >
                {glossary.subjects[id].subject.replace(/^中級/, '')}
              </button>
            ))}
          </div>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋中文、英文、定義或案例"
            className="lg:ml-auto w-full lg:w-[280px] rounded-lg border border-border px-3 py-2 text-[0.88rem] outline-none focus:border-accent"
          />
        </div>
      </div>

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
          <div className="p-5 text-text-light text-[0.9rem]">找不到符合條件的關鍵字。</div>
        )}
      </div>
    </div>
  )
}

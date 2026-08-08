import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loadAllMindmaps } from '../../data/guideMindmap'
import { buildChapterIndex, loadTopicHeat, type ChapterRef } from '../../data/topicHeat'
import type { TopicHeatChapter, TopicHeatData } from '../../types'

type Sort = 'count' | 'spread'

const ALL = '全部'

/**
 * 概念熱度軸：哪個觀念常考、它散落在哪幾章。
 *
 * 兩條規則跟章節熱度一致，改動前先讀 `playbook/08-topic-labeling.md` §7-3：
 * - **各章題數不可相加**：一題常引用數章，`chapters` 是分布不是份額。
 * - 長度只編碼題數，比例尺固定用全體最大值——切換大類篩選不會重新縮放，
 *   否則同一個概念在不同篩選下看起來長度不同。
 */
export default function TopicHeatPanel() {
  const navigate = useNavigate()
  const [data, setData] = useState<TopicHeatData | null>(null)
  const [chapters, setChapters] = useState<Map<string, ChapterRef> | null>(null)
  const [sort, setSort] = useState<Sort>('count')
  const [category, setCategory] = useState<string>(ALL)
  const [query, setQuery] = useState('')
  const [opened, setOpened] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([loadTopicHeat(), loadAllMindmaps()]).then(([heat, maps]) => {
      if (!active) return
      setData(heat)
      setChapters(buildChapterIndex(maps))
    })
    return () => {
      active = false
    }
  }, [])

  /** 這份採計下沒有題目的概念不列出——畫一條長度 0 的長條不是資訊。 */
  const scored = useMemo(
    () => (data ? data.topics.filter((topic) => topic.count > 0) : []),
    [data],
  )
  const unscored = (data?.topics.length ?? 0) - scored.length
  const peak = useMemo(() => Math.max(...scored.map((t) => t.count), 1), [scored])

  const categories = useMemo(() => {
    const tally = new Map<string, number>()
    for (const topic of scored) tally.set(topic.parent, (tally.get(topic.parent) ?? 0) + 1)
    return [...tally.entries()].sort((a, b) => b[1] - a[1])
  }, [scored])

  const rows = useMemo(() => {
    const keyword = query.trim()
    const filtered = scored.filter(
      (topic) =>
        (category === ALL || topic.parent === category) &&
        (keyword === '' || topic.name.includes(keyword) || topic.parent.includes(keyword)),
    )
    return filtered.sort((a, b) =>
      sort === 'count'
        ? b.count - a.count || b.guideChapterCount - a.guideChapterCount
        : b.guideChapterCount - a.guideChapterCount || b.count - a.count,
    )
  }, [scored, category, query, sort])

  const chapterRef = (chapter: TopicHeatChapter) =>
    chapters?.get(`${chapter.guideKey}:${chapter.nodeId}`)

  if (!data || !chapters) return <p className="mt-8 text-sm text-text-light">載入中…</p>

  return (
    <>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <span className="text-text-light">排序依據</span>
        {(
          [
            ['count', '常考題數'],
            ['spread', '散落章數'],
          ] as [Sort, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setSort(value)}
            className={`rounded border px-2.5 py-1 ${
              sort === value ? 'border-accent text-accent' : 'border-border text-text-light'
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-xs text-text-light">
          散落章數多，代表這個觀念不屬於任何單一章節，複習時要跨章一起看。
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        {[[ALL, scored.length] as [string, number], ...categories].map(([name, total]) => (
          <button
            key={name}
            type="button"
            onClick={() => setCategory(name)}
            className={`rounded border px-2.5 py-1 ${
              category === name ? 'border-accent bg-accent text-white' : 'border-border text-app-text'
            }`}
          >
            {name}
            <span className={`ml-1.5 text-xs ${category === name ? 'text-white/80' : 'text-text-light'}`}>
              {total}
            </span>
          </button>
        ))}
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜尋概念"
          aria-label="搜尋概念"
          className="rounded border border-border bg-card px-2.5 py-1 text-sm text-app-text placeholder:text-text-light"
        />
      </div>

      <ol className="mt-4 divide-y divide-border rounded border border-border bg-card">
        {rows.map((topic, position) => {
          const isOpen = opened === topic.name
          return (
            <li key={topic.name}>
              <button
                type="button"
                onClick={() => setOpened(isOpen ? null : topic.name)}
                aria-expanded={isOpen}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-app-bg"
              >
                <span className="w-6 shrink-0 text-right text-xs tabular-nums text-text-light">
                  {position + 1}
                </span>
                <span
                  className="w-28 shrink-0 truncate text-sm text-app-text sm:w-40"
                  title={topic.name}
                >
                  {topic.name}
                </span>
                {/* 固定寬度的軌道，百分比相對軌道算——直接把 % 寬度放在 flex item 上
                    會被容器寬度與 max-width 夾住，長度編碼會失效（22 題與 11 題等長）。 */}
                <span className="hidden w-36 shrink-0 sm:block" aria-hidden="true">
                  <span
                    className="block h-2 min-w-[2px] rounded-r bg-accent"
                    style={{ width: `${(topic.count / peak) * 100}%` }}
                  />
                </span>
                <span className="ml-auto shrink-0 text-sm tabular-nums text-app-text">
                  {topic.count} 題
                </span>
                <span className="w-24 shrink-0 text-right text-xs tabular-nums text-text-light">
                  {topic.guideChapterCount > 0
                    ? `散落 ${topic.guideChapterCount} 章`
                    : '無章節標註'}
                </span>
              </button>

              {isOpen && (
                <div className="border-t border-border bg-app-bg px-3 py-3">
                  <p className="text-xs text-text-light">
                    {topic.parent}
                    {topic.chapterCount > 0 ? (
                      <>
                        ・出現在以下章節，
                        <strong>各章數字不可相加</strong>（一題常同時引用數章）
                      </>
                    ) : (
                      <>・這些題目沒有章節標註，章節標註只建立在公告試題上</>
                    )}
                  </p>
                  {(
                    [
                      ['guide', '學習指引'],
                      ['outline', '官方大綱'],
                    ] as [TopicHeatChapter['kind'], string][]
                  ).map(([kind, label]) => {
                    const group = topic.chapters.filter((chapter) => chapter.kind === kind)
                    if (group.length === 0) return null
                    return (
                      <div key={kind} className="mt-2 flex flex-wrap items-center gap-1.5">
                        <span className="mr-1 text-xs text-text-light">{label}</span>
                        {group.map((chapter) => {
                          const ref = chapterRef(chapter)
                          return (
                            <button
                              key={`${chapter.guideKey}:${chapter.nodeId}`}
                              type="button"
                              disabled={!ref?.route}
                              onClick={() => ref?.route && navigate(ref.route)}
                              title={ref?.subject}
                              className="rounded border border-border bg-card px-2 py-1 text-xs text-app-text enabled:hover:border-accent enabled:hover:text-accent disabled:text-text-light"
                            >
                              {ref?.title ?? chapter.nodeId}
                              <span className="ml-1.5 tabular-nums text-text-light">
                                {chapter.count}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              )}
            </li>
          )
        })}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-text-light">沒有符合的概念</li>
        )}
      </ol>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className="text-xs text-text-light">
          <h2 className="text-base font-semibold text-primary">怎麼看這個軸</h2>
          <ul className="mt-2 space-y-1.5">
            <li>
              統計自 {data.questionCount} 題歷屆公告試題的考點，共 {data.topicCount} 個觀念。
              一題常同時考到數個觀念，<strong>各項數字不能相加</strong>。
            </li>
            <li>
              「散落章數」是這個軸最有用的欄位：只集中在少數幾章的觀念可以單章讀完，
              散在十幾章的觀念得跨章整理。
            </li>
            <li>
              同一份內容有「學習指引」與「官方大綱」兩套章節層級，散落章數只算學習指引，
              避免同一段內容被算成兩章；展開後兩套都會列出。
            </li>
            <li>
              點任一列展開章節分布，再點章節名稱可直接前往該章。
              {data.questionsWithoutChapter > 0 && (
                <>
                  其中 {data.questionsWithoutChapter} 題尚未對到章節，
                  展開後會標示「無章節標註」。
                </>
              )}
            </li>
            {unscored > 0 && (
              <li>另有 {unscored} 個觀念目前沒有可採計的題目，因此不列在上表。</li>
            )}
          </ul>
        </div>
        <div className="text-xs text-text-light">
          <h2 className="text-base font-semibold text-primary">與章節熱度的差別</h2>
          <p className="mt-2">
            章節軸回答「哪一章考得多」，適合安排讀書順序；概念軸回答「哪個觀念反覆出現」，
            適合考前收斂重點。兩者名次不會一致——最熱的觀念往往橫跨好幾章，
            在章節軸上會被拆散成好幾個中等大小的節點。
          </p>
        </div>
      </div>
    </>
  )
}

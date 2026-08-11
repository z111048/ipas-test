import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import SpriteText from 'three-spritetext'

interface ConceptNodeInput {
  name: string
  parent: string
  questionCount: { official: number; practice: number }
  related: { name: string; weight: number }[]
}

interface GraphNode {
  id: string
  parent: string
  official: number
  total: number
  val: number
  color: string
}

interface GraphLink {
  source: string
  target: string
  weight: number
}

// 單一藍色階（sequential，magnitude 用），5 階由淺到深。
// 依 dataviz 的 ordinal 規則驗過：單一色相、亮度單調、階距 ≥0.06、
// 最淺階對淺色底 2.06:1（scripts/validate_palette.js --ordinal --mode light 全 PASS）。
// ⚠️ 不要改成「8 個分類各一色」：8 色只在相鄰配對下過關，力導向圖任兩點都可能
// 相鄰（all-pairs），那個配置過不了色盲與一般視覺的分辨門檻。分類靠篩選與標籤帶。
const HEAT_STEPS = ['#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#104281']
const MUTED = '#c9ced6'
const HIGHLIGHT = '#eb6834'
const LINK_COLOR = 'rgba(120,132,150,0.35)'
const LINK_STRONG = 'rgba(235,104,52,0.9)'

// force-graph 會就地把 link.source/target 從字串換成節點物件，所以兩種都要能讀。
// 只比字串的話，第一次 tick 之後所有高亮就會失效。
function endId(end: unknown): string {
  return typeof end === 'string' ? end : String((end as { id?: string })?.id ?? '')
}

function heatColor(official: number, max: number): string {
  if (official <= 0) return HEAT_STEPS[0]
  const ratio = Math.sqrt(official / Math.max(max, 1))
  return HEAT_STEPS[Math.min(HEAT_STEPS.length - 1, Math.floor(ratio * HEAT_STEPS.length))]
}

interface Props {
  concepts: ConceptNodeInput[]
  selected: string
  minWeight: number
  onSelect: (name: string) => void
}

export default function ConceptGraph3D({ concepts, selected, minWeight, onSelect }: Props) {
  const wrapper = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)

  useEffect(() => {
    const element = wrapper.current
    if (!element) return
    const observer = new ResizeObserver(() => setWidth(element.clientWidth))
    observer.observe(element)
    setWidth(element.clientWidth)
    return () => observer.disconnect()
  }, [])

  const data = useMemo(() => {
    const maxOfficial = Math.max(...concepts.map((c) => c.questionCount.official), 1)
    const nodes: GraphNode[] = concepts.map((concept) => {
      const total = concept.questionCount.official + concept.questionCount.practice
      return {
        id: concept.name,
        parent: concept.parent,
        official: concept.questionCount.official,
        total,
        // 面積正比於題數，所以半徑開根號——直接拿題數當半徑會讓熱門概念大到蓋住整張圖
        val: Math.max(1, Math.sqrt(total)),
        color: heatColor(concept.questionCount.official, maxOfficial),
      }
    })
    const known = new Set(nodes.map((n) => n.id))
    const seen = new Set<string>()
    const links: GraphLink[] = []
    for (const concept of concepts) {
      for (const related of concept.related) {
        if (related.weight < minWeight || !known.has(related.name)) continue
        const key = [concept.name, related.name].sort().join('|')
        if (seen.has(key)) continue      // related 是雙向的，同一條邊會出現兩次
        seen.add(key)
        links.push({ source: concept.name, target: related.name, weight: related.weight })
      }
    }
    return { nodes, links }
  }, [concepts, minWeight])

  const neighbours = useMemo(() => {
    if (!selected) return new Set<string>()
    const set = new Set<string>([selected])
    for (const link of data.links) {
      const source = endId(link.source)
      const target = endId(link.target)
      if (source === selected) set.add(target)
      if (target === selected) set.add(source)
    }
    return set
  }, [data.links, selected])

  // 171 個標籤同時顯示會糊成一片：只有夠大的節點常駐標籤，其餘選到才出現
  const labelFloor = useMemo(() => {
    const totals = data.nodes.map((n) => n.total).sort((a, b) => b - a)
    return totals[Math.min(24, totals.length - 1)] ?? 0
  }, [data.nodes])

  return (
    <div ref={wrapper} className="rounded-xl border border-border bg-card overflow-hidden">
      <ForceGraph3D
        graphData={data}
        width={width}
        height={520}
        backgroundColor="#fcfcfb"
        showNavInfo={false}
        nodeRelSize={4}
        nodeVal={(node) => (node as GraphNode).val}
        nodeColor={(node) => {
          const item = node as GraphNode
          if (!selected) return item.color
          return neighbours.has(item.id) ? (item.id === selected ? HIGHLIGHT : item.color) : MUTED
        }}
        nodeThreeObjectExtend
        nodeThreeObject={(node: object) => {
          const item = node as GraphNode
          const show = item.id === selected || neighbours.has(item.id) || item.total >= labelFloor
          if (!show) return null as unknown as never
          const sprite = new SpriteText(item.id)
          sprite.color = item.id === selected ? HIGHLIGHT : '#334155'
          sprite.textHeight = item.id === selected ? 5 : 3.5
          // SpriteText 的型別宣告沒有帶到 Object3D 的 position，但執行期有
          ;(sprite as unknown as { position: { set: (x: number, y: number, z: number) => void } })
            .position.set(0, -(Math.cbrt(item.val) * 4 + 3), 0)
          return sprite as unknown as never
        }}
        linkColor={(link) => {
          const l = link as unknown as GraphLink
          if (!selected) return LINK_COLOR
          return endId(l.source) === selected || endId(l.target) === selected
            ? LINK_STRONG : LINK_COLOR
        }}
        linkWidth={(link) => Math.min(3, (link as unknown as GraphLink).weight)}
        linkOpacity={0.5}
        onNodeClick={(node) => onSelect((node as GraphNode).id)}
        enableNodeDrag={false}
        cooldownTicks={120}
      />
    </div>
  )
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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

// force-graph 會在 tick 時把座標直接寫回節點物件上，所以版面收斂後這些欄位才有值
type PositionedNode = GraphNode & { x?: number; y?: number; z?: number }

interface GraphLink {
  source: string
  target: string
  weight: number
}

// 深色底的單一藍色階（sequential，magnitude 用），暗 → 亮＝考得少 → 考得多。
// 對 #0e1526 這個底色驗過：validate_palette.js --ordinal --mode dark --surface "#0e1526"
// 四項全 PASS（亮度單調、階距 ≥0.06、最暗階 2.25:1、單一色相）。
// ⚠️ 不要改成「8 個分類各一色」：8 色配置只在相鄰配對下過關，力導向圖任兩點都可能
// 相鄰（all-pairs），那個配置過不了色盲與一般視覺的分辨門檻。分類靠篩選與標籤帶。
const HEAT_STEPS = ['#184f95', '#256abf', '#3987e5', '#6da7ec', '#b7d3f6']
const SURFACE = '#0e1526'
const MUTED = '#2b3550'
const HIGHLIGHT = '#f59e5b'
const LINK_COLOR = 'rgba(160,185,230,0.38)'
const LINK_STRONG = 'rgba(245,158,91,0.85)'
// zoomToFit 只保證「當下這個角度裝得下」。圖不是球形，自轉轉到較寬的側面時，
// 同一個距離就會切到邊（實測 22 秒與 60 秒兩張截圖分別被切在右邊與下緣）。
// 自轉半徑因此比「剛好裝下」的距離再退 10%。
// zoomToFit 的 padding 是像素，而畫布只有 560px 高：原本的 60px 等於上下各砍掉
// 10.7%，核心因此只佔畫面高度 48%（實測 300×270 於 1088×560）。
const FIT_PADDING = 16
const GRAPH_HEIGHT = 560
const FOV_TAN = Math.tan((50 * Math.PI) / 180 / 2)  // 3d-force-graph 的預設 fov 是 50°
const LABEL_TARGET_PX = 14
const SPIN_MARGIN = 1.08
const LABEL_COLOR = '#dce6f7'

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

interface GraphHandle {
  cameraPosition: (
    position?: { x?: number; y?: number; z?: number },
    lookAt?: object,
    ms?: number,
  ) => { x: number; y: number; z: number }
  zoomToFit: (ms?: number, padding?: number, nodeFilter?: (node: object) => boolean) => void
}

interface Props {
  concepts: ConceptNodeInput[]
  selected: string
  minWeight: number
  onSelect: (name: string) => void
}

export default function ConceptGraph3D({ concepts, selected, minWeight, onSelect }: Props) {
  const wrapper = useRef<HTMLDivElement>(null)
  const graph = useRef<GraphHandle | null>(null)
  const [width, setWidth] = useState(800)
  const [hovered, setHovered] = useState<string | null>(null)
  const [spinning, setSpinning] = useState(true)
  // 對焦期間必須停掉自轉：自轉每 50ms 就把相機寫回 orbit 距離，會蓋掉 zoomToFit
  // 的動畫，於是「對焦後讀到的距離」讀到的其實是 orbit 自己——乘上留白係數就變成
  // 每對焦一次退遠一次（實測畫面越縮越小，主叢集剩畫面中央一小團）。
  const [fitting, setFitting] = useState(true)
  // 自轉半徑不能寫死：版面收斂後的實際大小差很多，寫死 420 會讓一半的球衝出畫面
  const [orbit, setOrbit] = useState(420)

  useEffect(() => {
    const element = wrapper.current
    if (!element) return
    const observer = new ResizeObserver(() => setWidth(element.clientWidth))
    observer.observe(element)
    setWidth(element.clientWidth)
    return () => observer.disconnect()
  }, [])

  // 緩慢自轉，讓靜止的圖看起來是活的；使用者一動就停，不跟操作搶控制權
  useEffect(() => {
    if (!spinning || fitting) return
    const distance = orbit
    let angle = 0
    const timer = window.setInterval(() => {
      angle += 0.004
      graph.current?.cameraPosition({
        x: distance * Math.sin(angle),
        y: distance * 0.18,
        z: distance * Math.cos(angle),
      })
    }, 50)
    return () => window.clearInterval(timer)
  }, [spinning, fitting, orbit])

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

  // 滑過優先於選取：滑鼠移到哪就亮到哪，移開才回到目前選的概念
  const focus = hovered ?? selected
  const neighbours = useMemo(() => {
    if (!focus) return new Set<string>()
    const set = new Set<string>([focus])
    for (const link of data.links) {
      const source = endId(link.source)
      const target = endId(link.target)
      if (source === focus) set.add(target)
      if (target === focus) set.add(source)
    }
    return set
  }, [data.links, focus])

  // 字級的單位是圖空間，不是像素：畫面上的高度 = textHeight × 畫布高 ÷ (2·距離·tan(fov/2))。
  // 寫死數值會隨每次力場收斂出的取景距離忽大忽小（實測 575～965 都出現過），
  // 所以反過來從距離回推：固定看起來約 14px。
  const labelUnit = useMemo(
    () => Math.min(28, Math.max(10, (orbit * LABEL_TARGET_PX) / (GRAPH_HEIGHT / (2 * FOV_TAN)))),
    [orbit])

  // 171 個標籤同時顯示會糊成一片：只有夠大的節點常駐標籤，其餘選到或滑過才出現
  const labelFloor = useMemo(() => {
    const totals = data.nodes.map((n) => n.total).sort((a, b) => b - a)
    return totals[Math.min(11, totals.length - 1)] ?? 0
  }, [data.nodes])

  const connected = useMemo(() => {
    const set = new Set<string>()
    for (const link of data.links) {
      set.add(endId(link.source))
      set.add(endId(link.target))
    }
    return set
  }, [data.links])

  const stopSpin = useCallback(() => setSpinning(false), [])

  // 版面收斂後讓 force-graph 自己算「剛好裝得下」的距離，再用那個距離自轉。
  // 寫死半徑會讓一半的球衝出畫面。
  //
  // 取景只用「核心」而不是整個包圍盒：實測有連線的節點裡也有幾個被斥力甩遠的，
  // 包圍盒被撐到 533，密集核心因此只佔畫面三分之一（zoomToFit 的 nodeFilter 本身
  // 是有效的：946 → 766，問題出在拿什麼餵它）。這裡再砍掉離重心最遠的 10%。
  const fitCamera = useCallback(() => {
    setFitting(true)
    const positioned = data.nodes.filter(
      (node) => connected.size === 0 || connected.has(node.id)) as PositionedNode[]
    const placed = positioned.filter((node) => Number.isFinite(node.x))
    let core: Set<string> | null = null
    if (placed.length >= 10) {
      const centre = ['x', 'y', 'z'].map((axis) => {
        const key = axis as 'x' | 'y' | 'z'
        return placed.reduce((sum, node) => sum + (node[key] ?? 0), 0) / placed.length
      })
      const withRadius = placed.map((node) => ({
        id: node.id,
        r: Math.hypot((node.x ?? 0) - centre[0], (node.y ?? 0) - centre[1],
                      (node.z ?? 0) - centre[2]),
      }))
      const cutoff = [...withRadius].sort((a, b) => a.r - b.r)[
        Math.floor(withRadius.length * 0.9)].r
      core = new Set(withRadius.filter((node) => node.r <= cutoff).map((node) => node.id))
    }
    graph.current?.zoomToFit(900, FIT_PADDING, (node) => {
      const id = String((node as { id?: string }).id ?? '')
      if (core) return core.has(id)
      return connected.size === 0 || connected.has(id)
    })
    window.setTimeout(() => {
      const position = graph.current?.cameraPosition()
      const distance = position
        ? Math.hypot(position.x, position.y, position.z)
        : Number.NaN
      if (Number.isFinite(distance) && distance > 0) setOrbit(distance * SPIN_MARGIN)
      setFitting(false)
    }, 1100)
  }, [connected, data.nodes])

  // ⚠️ 不能只靠 onEngineStop：力場的 tick 跟著畫格跑，沒有 GPU 加速的機器
  // （或分頁在背景時）200 個 tick 要花一分鐘以上，那之前畫面都是沒對準的。
  // 這裡固定 5 秒後先對一次，engine 真的停了再對一次。
  useEffect(() => {
    const timer = window.setTimeout(fitCamera, 5000)
    return () => window.clearTimeout(timer)
  }, [fitCamera, minWeight])

  return (
    <div
      ref={wrapper}
      onPointerDown={stopSpin}
      onWheel={stopSpin}
      className="relative rounded-xl border border-border overflow-hidden"
      style={{ backgroundColor: SURFACE }}
    >
      <ForceGraph3D
        ref={graph as never}
        graphData={data}
        width={width}
        height={GRAPH_HEIGHT}
        backgroundColor={SURFACE}
        showNavInfo={false}
        nodeRelSize={5}
        nodeResolution={16}
        nodeOpacity={0.95}
        nodeVal={(node) => (node as GraphNode).val}
        nodeColor={(node) => {
          const item = node as GraphNode
          if (!focus) return item.color
          if (item.id === focus) return HIGHLIGHT
          return neighbours.has(item.id) ? item.color : MUTED
        }}
        nodeThreeObjectExtend
        nodeThreeObject={(node: object) => {
          const item = node as GraphNode
          const show = item.id === focus || neighbours.has(item.id) || item.total >= labelFloor
          if (!show) return null as unknown as never
          const sprite = new SpriteText(item.id)
          sprite.color = item.id === focus ? HIGHLIGHT : LABEL_COLOR
          sprite.textHeight = item.id === focus ? labelUnit * 1.35 : labelUnit
          // SpriteText 的型別宣告沒有帶到 Object3D 的 position，但執行期有
          ;(sprite as unknown as { position: { set: (x: number, y: number, z: number) => void } })
            .position.set(0, -(Math.cbrt(item.val) * 4 + 6), 0)
          return sprite as unknown as never
        }}
        linkCurvature={0.18}
        linkColor={(link) => {
          const l = link as unknown as GraphLink
          if (!focus) return LINK_COLOR
          return endId(l.source) === focus || endId(l.target) === focus ? LINK_STRONG : LINK_COLOR
        }}
        linkWidth={(link) => Math.min(3, (link as unknown as GraphLink).weight)}
        linkOpacity={0.55}
        // 沿線跑的光點只給強關聯（同題出現 ≥2 次），弱關聯保持安靜——
        // 全部都跑會變成滿畫面雜訊，也會讓 15% 的「過廣」標籤看起來像重點
        linkDirectionalParticles={(link) => {
          const weight = (link as unknown as GraphLink).weight
          return weight >= 2 ? Math.min(3, weight) : 0
        }}
        linkDirectionalParticleWidth={1.6}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleColor={() => LINK_STRONG}
        onNodeHover={(node) => setHovered(node ? (node as GraphNode).id : null)}
        onNodeClick={(node) => {
          setSpinning(false)
          onSelect((node as GraphNode).id)
        }}
        onBackgroundClick={stopSpin}
        enableNodeDrag={false}
        cooldownTicks={200}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        onEngineStop={fitCamera}
      />
      {spinning && (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-white/10 px-3 py-1 text-[0.72rem] text-white/70">
          自動旋轉中 · 拖曳或點擊即停
        </div>
      )}
    </div>
  )
}

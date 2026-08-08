import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined, CompressOutlined } from '@ant-design/icons'
import {
  App, Button, Card, Checkbox, Descriptions, Empty, Input, Select, Space, Spin, Statistic,
  Tag, Typography,
} from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Kb } from '../types'

const { Title, Text } = Typography

// ---------- 与 Python GraphData / GraphStats 契约对齐 ----------

interface GraphNode {
  id: string
  label: string
  kind: 'entity' | 'chunk'
  entity_type?: string
  doc_id?: string
  source_file?: string
}

interface GraphEdge {
  source: string
  target: string
  label: string
  kind: 'relates' | 'mentioned'
}

interface GraphData {
  kb_id: string
  enabled: boolean
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated: boolean
}

interface GraphStats {
  kb_id: string
  enabled: boolean
  entity_count: number
  relation_count: number
  chunk_count: number
}

// ---------- 布局 ----------

const VIEW_W = 960
const VIEW_H = 640
const ENTITY_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#faad14', '#2f54eb']

function colorOf(type: string): string {
  if (!type) return '#1677ff'
  let h = 0
  for (const ch of type) h = (h * 31 + ch.charCodeAt(0)) % 997
  return ENTITY_COLORS[h % ENTITY_COLORS.length]
}

interface Pos { x: number; y: number }

/**
 * 按实体类型分列布局（替代力导向）：
 * 同类型实体排在同一列（按度数降序、上下错位两排），类型间用列隔开，
 * 结构清晰且天然避免节点/标签互相挤压。出处块统一放底部一行。
 */
function groupedLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Pos> {
  const pos = new Map<string, Pos>()
  const degree = new Map<string, number>()
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  }

  const entities = nodes.filter(n => n.kind === 'entity')
  const chunks = nodes.filter(n => n.kind === 'chunk')

  // 类型分组：最多 6 个主类型，其余并入"其他"
  const typeCount = new Map<string, number>()
  for (const nd of entities) {
    const t = nd.entity_type || '未分类'
    typeCount.set(t, (typeCount.get(t) ?? 0) + 1)
  }
  const topTypes = [...typeCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([t]) => t)
  const groups = new Map<string, GraphNode[]>()
  for (const nd of entities) {
    let t = nd.entity_type || '未分类'
    if (!topTypes.includes(t)) t = '其他'
    const list = groups.get(t) ?? []
    list.push(nd)
    groups.set(t, list)
  }
  const groupNames = [...groups.keys()]
    .sort((a, b) => groups.get(b)!.length - groups.get(a)!.length)

  const colW = VIEW_W / groupNames.length
  groupNames.forEach((g, gi) => {
    const list = groups.get(g)!.sort((a, b) =>
      (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
    const cx = colW * (gi + 0.5)
    list.forEach((nd, i) => {
      const y = VIEW_H * (i + 1) / (list.length + 1)
      const x = cx + (i % 2 === 0 ? -colW * 0.18 : colW * 0.18)
      pos.set(nd.id, { x, y })
    })
  })

  // 出处块：底部一行
  chunks.forEach((nd, i) => {
    pos.set(nd.id, { x: VIEW_W * (i + 1) / (chunks.length + 1), y: VIEW_H - 26 })
  })
  return pos
}

interface Selected { type: 'node' | 'edge'; node?: GraphNode; edge?: GraphEdge }

// ---------- 标签碰撞检测 ----------

interface Rect { x: number; y: number; w: number; h: number }

function truncateLabel(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}

function labelSize(text: string, fontSize: number): { w: number; h: number } {
  let cjk = 0
  let latin = 0
  for (const ch of text) {
    if (ch.charCodeAt(0) > 127) cjk++
    else latin++
  }
  return { w: cjk * fontSize + latin * fontSize * 0.62 + 6, h: fontSize + 4 }
}

function rectsOverlap(a: Rect, b: Rect, pad = 2): boolean {
  return a.x < b.x + b.w + pad && a.x + a.w + pad > b.x
    && a.y < b.y + b.h + pad && a.y + a.h + pad > b.y
}

/** 计算哪些实体标签可以显示：不与任何节点/其他标签重叠才保留。 */
function visibleEntityLabels(nodes: GraphNode[], positions: Map<string, Pos>,
                             edges: GraphEdge[]): Set<string> {
  const circles = nodes
    .map(nd => {
      const p = positions.get(nd.id)
      return p ? { id: nd.id, kind: nd.kind, x: p.x, y: p.y, r: nd.kind === 'entity' ? 11 : 7 } : null
    })
    .filter((c): c is { id: string; kind: GraphNode['kind']; x: number; y: number; r: number } => c !== null)

  const degree = new Map<string, number>()
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  }
  const nodesById = new Map(nodes.map(nd => [nd.id, nd]))
  const entities = circles
    .filter(c => c.kind === 'entity')
    .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))

  const kept: Rect[] = []
  const visible = new Set<string>()
  for (const c of entities) {
    const label = truncateLabel(nodesById.get(c.id)?.label ?? '', 12)
    if (!label) continue
    const { w, h } = labelSize(label, 12)
    const rect: Rect = { x: c.x - w / 2, y: c.y + c.r + 6, w, h }
    // 标签压到任何节点圆 → 隐藏
    const hitNode = circles.some(other => {
      if (other.id === c.id) return false
      return rectsOverlap(rect, { x: other.x - other.r, y: other.y - other.r, w: other.r * 2, h: other.r * 2 }, 3)
    })
    if (hitNode) continue
    // 与其他已保留标签重叠 → 隐藏
    if (kept.some(r => rectsOverlap(r, rect, 4))) continue
    kept.push(rect)
    visible.add(c.id)
  }
  return visible
}

// ---------- 图谱画布 ----------

function GraphCanvas({
  nodes, edges, positions, keyword,
  selected, onSelect, onLayoutChanged,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  positions: Map<string, Pos>
  keyword: string
  selected: Selected | null
  onSelect: (s: Selected | null) => void
  onLayoutChanged?: (pos: Map<string, Pos>) => void
}) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [hoverId, setHoverId] = useState<string | null>(null)
  const drag = useRef<{ mode: 'pan' | 'node'; id?: string; startX: number; startY: number; panX: number; panY: number; nodeX: number; nodeY: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const kw = keyword.trim().toLowerCase()
  const dimmed = useMemo(() => {
    if (!kw) return new Set<string>()
    const s = new Set<string>()
    for (const nd of nodes) {
      if (nd.kind === 'entity' && !nd.label.toLowerCase().includes(kw)) s.add(nd.id)
    }
    return s
  }, [nodes, kw])

  const related = useMemo(() => {
    if (!selected?.node) return new Set<string>()
    const s = new Set<string>([selected.node.id])
    for (const e of edges) {
      if (e.source === selected.node.id || e.target === selected.node.id) {
        s.add(e.source)
        s.add(e.target)
      }
    }
    return s
  }, [selected, edges])

  const visibleLabels = useMemo(
    () => visibleEntityLabels(nodes, positions, edges),
    [nodes, positions, edges],
  )

  const toScreen = (p: Pos): Pos => ({
    x: p.x * zoom + pan.x,
    y: p.y * zoom + pan.y,
  })

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    const target = e.target as Element
    const nodeEl = target.closest('[data-node-id]')
    const nodeId = nodeEl?.getAttribute('data-node-id') ?? null
    const p = nodeId ? positions.get(nodeId) : undefined
    if (p && nodeId) {
      drag.current = { mode: 'node', id: nodeId, startX: e.clientX, startY: e.clientY, panX: 0, panY: 0, nodeX: p.x, nodeY: p.y }
    } else {
      drag.current = { mode: 'pan', startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y, nodeX: 0, nodeY: 0 }
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    if (!d) return
    if (d.mode === 'pan') {
      setPan({ x: d.panX + (e.clientX - d.startX), y: d.panY + (e.clientY - d.startY) })
    } else if (d.id && d.mode === 'node') {
      const p = positions.get(d.id)
      if (p) {
        p.x = d.nodeX + (e.clientX - d.startX) / zoom
        p.y = d.nodeY + (e.clientY - d.startY) / zoom
        onLayoutChanged?.(positions)
      }
    }
  }

  const onPointerUp = () => { drag.current = null }

  const onWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    const next = Math.min(3, Math.max(0.25, zoom * factor))
    const cx = VIEW_W / 2
    const cy = VIEW_H / 2
    setPan({
      x: cx - (cx - pan.x) * (next / zoom),
      y: cy - (cy - pan.y) * (next / zoom),
    })
    setZoom(next)
  }

  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }) }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 2, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Button size="small" icon={<ZoomInOutlined />} onClick={() => { setZoom(z => Math.min(3, z * 1.2)) }} />
        <Button size="small" icon={<ZoomOutOutlined />} onClick={() => { setZoom(z => Math.max(0.25, z / 1.2)) }} />
        <Button size="small" icon={<CompressOutlined />} onClick={reset} />
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        style={{ width: '100%', height: 640, background: '#fafafa', borderRadius: 8, cursor: 'grab', touchAction: 'none' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onWheel={onWheel}
        onMouseLeave={() => setHoverId(null)}
      >
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="16" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#8c8c8c" />
          </marker>
        </defs>
        <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
          {edges.map((edge, i) => {
            const a = positions.get(edge.source)
            const b = positions.get(edge.target)
            if (!a || !b) return null
            const len = Math.hypot(b.x - a.x, b.y - a.y)
            const active = selected?.edge === edge || (selected?.node && (related.has(edge.source) && related.has(edge.target)))
            const isRelates = edge.kind === 'relates'
            const stroke = active ? '#1677ff' : isRelates ? '#8c8c8c' : '#d9d9d9'
            const dash = isRelates ? undefined : '5 4'
            return (
              <g key={i}>
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={stroke} strokeWidth={active ? 2.4 : 1.2}
                  strokeDasharray={dash}
                  markerEnd={isRelates ? 'url(#arrow)' : undefined}
                  style={{ cursor: 'pointer' }}
                  onClick={ev => { ev.stopPropagation(); onSelect({ type: 'edge', edge }) }}
                  onMouseEnter={e => { e.currentTarget.style.strokeWidth = '2.4' }}
                  onMouseLeave={e => { e.currentTarget.style.strokeWidth = active ? '2.4' : '1.2' }}
                />
                {isRelates && edge.label && (selected?.edge === edge || (zoom >= 0.9 && len >= 130)) && (
                  <text
                    x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4}
                    fontSize={11} fill="#595959" textAnchor="middle"
                    style={{ pointerEvents: 'none', userSelect: 'none', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3, strokeLinejoin: 'round' }}
                  >
                    {truncateLabel(edge.label, 12)}
                  </text>
                )}
              </g>
            )
          })}
          {nodes.map(nd => {
            const p = positions.get(nd.id)
            if (!p) return null
            const isEntity = nd.kind === 'entity'
            const r = isEntity ? (related.has(nd.id) || selected?.node?.id === nd.id ? 13 : 9) : 6
            const dim = dimmed.has(nd.id)
            const fill = isEntity ? colorOf(nd.entity_type || '') : '#d3adf7'
            const sel = selected?.node?.id === nd.id
            const hovered = hoverId === nd.id
            const dimByHover = hoverId != null && !hovered && !sel && !related.has(nd.id)
            const showLabel = isEntity
              ? (hovered || sel || (zoom >= 0.7 && visibleLabels.has(nd.id)))
              : (hovered || sel)
            return (
              <g
                key={nd.id}
                data-node-id={nd.id}
                style={{ cursor: 'grab', opacity: dim ? 0.18 : dimByHover ? 0.4 : 1 }}
                onClick={e => { e.stopPropagation(); onSelect({ type: 'node', node: nd }) }}
                onMouseEnter={() => setHoverId(nd.id)}
                onMouseLeave={() => setHoverId(h => (h === nd.id ? null : h))}
              >
                <circle cx={p.x} cy={p.y} r={r + (sel ? 4 : 0)}
                        fill={fill} fillOpacity={0.85}
                        stroke={sel ? '#fa8c16' : '#fff'} strokeWidth={sel ? 3 : 1.5} />
                {showLabel && (
                  <text
                    x={p.x} y={p.y + r + 12}
                    fontSize={isEntity ? 12 : 10}
                    fill={isEntity ? '#262626' : '#722ed1'}
                    textAnchor="middle"
                    style={{ pointerEvents: 'none', userSelect: 'none', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3, strokeLinejoin: 'round' }}
                  >
                    {isEntity ? truncateLabel(nd.label, 12) : truncateLabel(nd.id.slice(2), 18)}
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}

// ---------- 主页面 ----------

export default function GraphPage() {
  const { message } = App.useApp()
  const [kbs, setKbs] = useState<Kb[]>([])
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null)
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [selected, setSelected] = useState<Selected | null>(null)
  const [positions, setPositions] = useState<Map<string, Pos>>(new Map())
  const [showChunks, setShowChunks] = useState(false)
  const [maxEntities, setMaxEntities] = useState(100)

  const load = async (kbId: number | null) => {
    if (kbId === null) {
      setGraph(null)
      setStats(null)
      return
    }
    setLoading(true)
    try {
      const [g, s] = await Promise.all([
        api.get<GraphData>(`/api/kb/${kbId}/graph?limit=400`),
        api.get<GraphStats>(`/api/kb/${kbId}/graph/stats`),
      ])
      setGraph(g)
      setStats(s)
      setSelected(null)
      setKeyword('')
    } catch (err) {
      message.error((err as Error).message || '图谱加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.get<Kb[]>('/api/kb').then(async list => {
      setKbs(list)
      if (list.length === 0) return
      // 优先选择已有图谱数据的知识库（避免默认选中空库造成"没有数据"的困惑）
      const statsList = await Promise.all(list.map(async kb => {
        try {
          const s = await api.get<GraphStats>(`/api/kb/${kb.id}/graph/stats`)
          return { kb, entityCount: s.entity_count ?? 0 }
        } catch {
          return { kb, entityCount: 0 }
        }
      }))
      const picked = statsList.find(x => x.entityCount > 0)?.kb ?? list[0]
      setSelectedKbId(picked.id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    void load(selectedKbId)
  }, [selectedKbId])

  // 按度数取前 N 个实体；可选是否显示出处块
  const visibleEntities = useMemo(() => {
    const all = (graph?.nodes ?? []).filter(n => n.kind === 'entity')
    if (!maxEntities || all.length <= maxEntities) return all
    const degree = new Map<string, number>()
    for (const e of graph?.edges ?? []) {
      if (e.kind !== 'relates') continue
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
    }
    return [...all]
      .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
      .slice(0, maxEntities)
  }, [graph, maxEntities])

  const visibleIds = useMemo(
    () => new Set(visibleEntities.map(n => n.id)),
    [visibleEntities],
  )

  const visibleChunks = useMemo(() => {
    if (!showChunks || !graph) return []
    const chunkIds = new Set<string>()
    for (const e of graph.edges) {
      if (e.kind === 'mentioned' && visibleIds.has(e.source)) chunkIds.add(e.target)
    }
    return graph.nodes.filter(n => n.kind === 'chunk' && chunkIds.has(n.id))
  }, [graph, showChunks, visibleIds])

  const visibleChunkIds = useMemo(
    () => new Set(visibleChunks.map(n => n.id)),
    [visibleChunks],
  )

  const visibleNodes = useMemo(
    () => [...visibleEntities, ...visibleChunks],
    [visibleEntities, visibleChunks],
  )

  const visibleEdges = useMemo(
    () => (graph?.edges ?? []).filter(e =>
      e.kind === 'relates'
        ? visibleIds.has(e.source) && visibleIds.has(e.target)
        : showChunks && visibleIds.has(e.source) && visibleChunkIds.has(e.target)),
    [graph, visibleIds, visibleChunkIds, showChunks],
  )

  useEffect(() => {
    if (visibleNodes.length === 0) {
      setPositions(new Map())
      return
    }
    setPositions(groupedLayout(visibleNodes, visibleEdges))
  }, [visibleNodes, visibleEdges])

  const legend = useMemo(() => {
    const m = new Map<string, number>()
    for (const nd of visibleEntities) {
      const t = nd.entity_type || '未分类'
      m.set(t, (m.get(t) ?? 0) + 1)
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)
  }, [visibleEntities])

  const totalEntities = graph?.nodes.filter(n => n.kind === 'entity').length ?? 0
  const empty = !graph || !graph.enabled || graph.nodes.length === 0
  const entityCount = stats?.entity_count ?? graph?.nodes.filter(n => n.kind === 'entity').length ?? 0

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>知识图谱</Title>
          <Text type="secondary">
            基于 Neo4j 的实体关系图谱：入库时自动抽取实体与关系，问答时图谱通道与向量检索融合
          </Text>
        </div>
        <Space wrap>
          <Select
            style={{ width: 240 }}
            placeholder="选择知识库"
            value={selectedKbId}
            onChange={setSelectedKbId}
            options={kbs.map(k => ({ value: k.id, label: k.name }))}
          />
          <Input
            style={{ width: 200 }}
            placeholder="高亮实体，如：Milvus"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            allowClear
          />
          <Select
            style={{ width: 150 }}
            value={maxEntities}
            onChange={setMaxEntities}
            options={[
              { value: 50, label: '核心 50 个实体' },
              { value: 100, label: '核心 100 个实体' },
              { value: 200, label: '核心 200 个实体' },
              { value: 0, label: '全部实体' },
            ]}
          />
          <Checkbox checked={showChunks} onChange={e => setShowChunks(e.target.checked)}>
            显示出处块
          </Checkbox>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load(selectedKbId)}>
            刷新
          </Button>
          <Button href="http://localhost:7474" target="_blank">Neo4j Browser</Button>
        </Space>
      </Space>

      <Space size={16} style={{ margin: '16px 0' }}>
        <Card size="small" style={{ minWidth: 140 }}>
          <Statistic title="实体" value={entityCount} />
        </Card>
        <Card size="small" style={{ minWidth: 140 }}>
          <Statistic title="关系" value={stats?.relation_count ?? 0} />
        </Card>
        <Card size="small" style={{ minWidth: 140 }}>
          <Statistic title="出处块" value={stats?.chunk_count ?? 0} />
        </Card>
      </Space>

      {legend.length > 0 && (
        <Space wrap style={{ margin: '0 0 12px' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>按类型分列：</Text>
          {legend.map(([t, count]) => (
            <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: colorOf(t), display: 'inline-block' }} />
              {t} ({count})
            </span>
          ))}
        </Space>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
      ) : empty ? (
        <Card>
          <Empty
            description={
              <Space direction="vertical" size={4}>
                <Text>该知识库还没有图谱数据</Text>
                <Text type="secondary">
                  {!graph?.enabled
                    ? '知识图谱功能已关闭（RAG_GRAPH_ENABLED=false）'
                    : '上传并解析文档后会自动构建；或检查 Neo4j 服务是否已启动（docker compose up -d neo4j）'}
                </Text>
              </Space>
            }
          />
        </Card>
      ) : (
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {graph!.truncated && (
              <Text type="warning" style={{ display: 'block', marginBottom: 8 }}>
                图谱较大，当前只展示部分节点（limit=400），可在 Neo4j Browser 中查看完整数据
              </Text>
            )}
            {maxEntities > 0 && totalEntities > maxEntities && (
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                当前展示度数最高的 {visibleEntities.length} / {totalEntities} 个实体
                （可在右上角"核心实体"下拉调整）
              </Text>
            )}
            <GraphCanvas
              nodes={visibleNodes}
              edges={visibleEdges}
              positions={positions}
              keyword={keyword}
              selected={selected}
              onSelect={setSelected}
              onLayoutChanged={pos => setPositions(new Map(pos))}
            />
            <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
              同类型实体按列排布 · 拖拽空白处平移 · 滚轮缩放 · 拖拽节点调整布局 · 点击查看详情
            </Text>
          </div>

          <Card size="small" style={{ width: 320, flexShrink: 0 }}>
            {!selected ? (
              <Text type="secondary">点击图谱中的节点或关系查看详情</Text>
            ) : selected.type === 'node' && selected.node ? (
              <div>
                <Space>
                  {selected.node.kind === 'entity'
                    ? <Tag color="blue">实体</Tag>
                    : <Tag color="purple">出处块</Tag>}
                  {selected.node.entity_type && <Tag>{selected.node.entity_type}</Tag>}
                </Space>
                <Title level={5} style={{ marginTop: 12 }}>{selected.node.label}</Title>
                {selected.node.kind === 'entity' ? (() => {
                  const nodeId = selected.node!.id
                  const rels = (graph?.edges ?? []).filter(e =>
                    e.kind === 'relates' && (e.source === nodeId || e.target === nodeId))
                  const chunks = (graph?.edges ?? []).filter(e =>
                    e.kind === 'mentioned' && e.source === nodeId)
                  const otherLabel = (e: GraphEdge) =>
                    (e.source === nodeId ? e.target : e.source).replace(/^e:/, '')
                  return (
                    <div style={{ fontSize: 12, lineHeight: 1.9 }}>
                      <Text type="secondary">直接关系（{rels.length} 条）</Text>
                      <div style={{ maxHeight: 220, overflow: 'auto', margin: '4px 0 12px' }}>
                        {rels.slice(0, 40).map((e, i) => (
                          <div key={i}>
                            <span style={{ color: '#595959' }}>
                              {e.source === nodeId ? '→' : '←'} {e.label || '相关'}
                            </span>{' '}
                            <Text>{otherLabel(e)}</Text>
                          </div>
                        ))}
                        {rels.length > 40 && <Text type="secondary">… 其余 {rels.length - 40} 条</Text>}
                      </div>
                      <Text type="secondary">出处块（{chunks.length} 个）</Text>
                      <div style={{ maxHeight: 160, overflow: 'auto', margin: '4px 0 0' }}>
                        {chunks.slice(0, 12).map((e, i) => (
                          <div key={i} style={{ color: '#8c8c8c', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {e.target.slice(2)} · {e.label || ''}
                          </div>
                        ))}
                        {chunks.length > 12 && <Text type="secondary">… 其余 {chunks.length - 12} 个</Text>}
                      </div>
                    </div>
                  )
                })() : (
                  <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
                    <Descriptions.Item label="文档">
                      {selected.node.source_file || selected.node.doc_id || '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="块 ID">
                      <Text copyable style={{ fontSize: 12 }}>{selected.node.id.slice(2)}</Text>
                    </Descriptions.Item>
                  </Descriptions>
                )}
              </div>
            ) : selected.edge ? (
              <div>
                <Tag color={selected.edge.kind === 'relates' ? 'geekblue' : 'default'}>
                  {selected.edge.kind === 'relates' ? '关系' : '出处'}
                </Tag>
                <Descriptions column={1} size="small" style={{ marginTop: 12 }}>
                  <Descriptions.Item label="起点">
                    {selected.edge.source.replace(/^e:/, '')}
                  </Descriptions.Item>
                  <Descriptions.Item label="关系">
                    {selected.edge.label || (selected.edge.kind === 'mentioned' ? '提及于' : '-')}
                  </Descriptions.Item>
                  <Descriptions.Item label="终点">
                    {selected.edge.target.replace(/^e:/, '')}
                  </Descriptions.Item>
                </Descriptions>
              </div>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  )
}

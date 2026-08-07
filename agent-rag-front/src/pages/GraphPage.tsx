import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined, CompressOutlined } from '@ant-design/icons'
import {
  App, Button, Card, Descriptions, Empty, Input, Select, Space, Spin, Statistic,
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

function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Pos> {
  const pos = new Map<string, Pos>()
  const n = nodes.length
  const cx = VIEW_W / 2
  const cy = VIEW_H / 2
  const radius = Math.max(180, Math.sqrt(Math.max(n, 1)) * 46)
  nodes.forEach((nd, i) => {
    const angle = (i / Math.max(n, 1)) * Math.PI * 2
    pos.set(nd.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) })
  })

  // 简易力导向：斥力 + 弹簧 + 向心
  const repulsion = 260000
  const spring = 0.02
  const ideal = 90
  for (let iter = 0; iter < 140; iter++) {
    const arr = Array.from(pos.entries())
    for (let i = 0; i < arr.length; i++) {
      for (let j = i + 1; j < arr.length; j++) {
        const [ida, a] = arr[i]
        const [idb, b] = arr[j]
        const dx = a.x - b.x
        const dy = a.y - b.y
        const d2 = Math.max(dx * dx + dy * dy, 1)
        const f = Math.min(repulsion / d2, 60)
        const d = Math.sqrt(d2)
        const fx = (dx / d) * f
        const fy = (dy / d) * f
        pos.set(ida, { x: a.x + fx, y: a.y + fy })
        pos.set(idb, { x: b.x - fx, y: b.y - fy })
      }
    }
    for (const e of edges) {
      const a = pos.get(e.source)
      const b = pos.get(e.target)
      if (!a || !b) continue
      const dx = b.x - a.x
      const dy = b.y - a.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const f = (d - ideal) * spring
      const fx = (dx / d) * f
      const fy = (dy / d) * f
      pos.set(e.source, { x: a.x + fx, y: a.y + fy })
      pos.set(e.target, { x: b.x - fx, y: b.y - fy })
    }
    for (const [id, p] of pos) {
      const gx = (cx - p.x) * 0.012
      const gy = (cy - p.y) * 0.012
      pos.set(id, { x: p.x + gx, y: p.y + gy })
    }
  }
  return pos
}

interface Selected { type: 'node' | 'edge'; node?: GraphNode; edge?: GraphEdge }

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
                {isRelates && edge.label && zoom > 0.6 && (
                  <text
                    x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4}
                    fontSize={11} fill="#595959" textAnchor="middle"
                    style={{ pointerEvents: 'none' }}
                  >
                    {edge.label.length > 14 ? edge.label.slice(0, 14) + '…' : edge.label}
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
            return (
              <g
                key={nd.id}
                data-node-id={nd.id}
                style={{ cursor: 'grab', opacity: dim ? 0.18 : 1 }}
                onClick={e => { e.stopPropagation(); onSelect({ type: 'node', node: nd }) }}
              >
                <circle cx={p.x} cy={p.y} r={r + (sel ? 4 : 0)}
                        fill={fill} fillOpacity={0.85}
                        stroke={sel ? '#fa8c16' : '#fff'} strokeWidth={sel ? 3 : 1.5} />
                <text
                  x={p.x} y={p.y + r + 12}
                  fontSize={isEntity ? 12 : 9} fill="#262626" textAnchor="middle"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {isEntity ? nd.label : '块'}
                </text>
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
      if (g.enabled && g.nodes.length > 0) {
        setPositions(computeLayout(g.nodes, g.edges))
      } else {
        setPositions(new Map())
      }
    } catch (err) {
      message.error((err as Error).message || '图谱加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.get<Kb[]>('/api/kb').then(list => {
      setKbs(list)
      if (list.length > 0) {
        setSelectedKbId(list[0].id)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    void load(selectedKbId)
  }, [selectedKbId])

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
            <GraphCanvas
              nodes={graph!.nodes}
              edges={graph!.edges}
              positions={positions}
              keyword={keyword}
              selected={selected}
              onSelect={setSelected}
              onLayoutChanged={pos => setPositions(new Map(pos))}
            />
            <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
              拖拽空白处平移 · 滚轮缩放 · 拖拽节点调整布局 · 点击节点/关系查看详情
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
                <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
                  {selected.node.kind === 'entity' && (
                    <Descriptions.Item label="类型">
                      {selected.node.entity_type || '未知'}
                    </Descriptions.Item>
                  )}
                  {selected.node.kind === 'chunk' && (
                    <>
                      <Descriptions.Item label="文档">
                        {selected.node.source_file || selected.node.doc_id || '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="块 ID">
                        <Text copyable style={{ fontSize: 12 }}>{selected.node.id.slice(2)}</Text>
                      </Descriptions.Item>
                    </>
                  )}
                </Descriptions>
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

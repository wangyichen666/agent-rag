import { SearchOutlined } from '@ant-design/icons'
import {
  App, Button, Card, Descriptions, Input, Select,
  Space, Table, Tag, Typography, Result,
} from 'antd'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Kb } from '../types'

const { Text } = Typography

// ---------- Trace 数据类型（与 Python DebugTraceResponse 对齐）----------

interface DenseResultItem {
  chunk_id: string; doc_id: string; source_file: string
  title_path: string[]; page?: number
  content: string; score: number; rank: number
}

interface CandidateItem {
  chunk_id: string; doc_id: string; source_file: string
  title_path: string[]; page?: number
  content: string; dense_rank?: number; dense_score?: number
  sparse_rank?: number; rrf_score: number; rerank_score?: number
}

interface TraceData {
  query: string; rewritten_query: string
  embedding_dim: number; embedding_preview: number[]
  dense_results: DenseResultItem[]; dense_count: number; has_sparse: boolean
  rrf_candidates: CandidateItem[]; rrf_count: number
  rerank_candidates: CandidateItem[]; rerank_degraded: boolean; rerank_count: number
  final_candidates: CandidateItem[]; final_count: number; threshold_applied: number
  system_prompt: string; user_prompt: string; full_prompt: string
}

// ---------- 辅助组件 ----------

function ScoreBar({ score, max = 1.0, label }: { score: number; max?: number; label?: string }) {
  const pct = Math.min(score / max * 100, 100)
  const color = pct > 70 ? '#52c41a' : pct > 30 ? '#faad14' : '#ff4d4f'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {label && <Text type="secondary" style={{ fontSize: 12, minWidth: 56 }}>{label}</Text>}
      <div style={{ flex: 1, height: 8, background: '#f0f0f0', borderRadius: 4 }}>
        <div style={{ width: `${pct}%`, height: 8, background: color, borderRadius: 4 }} />
      </div>
      <Text strong style={{ fontSize: 12, minWidth: 48, textAlign: 'right' }}>
        {score.toFixed(4)}
      </Text>
    </div>
  )
}

function ContentPreview({ content, maxLen = 500 }: { content: string; maxLen?: number }) {
  const truncated = content.length > maxLen ? content.slice(0, maxLen) + '...' : content
  return (
    <div style={{
      background: '#fafafa', padding: '8px 12px', borderRadius: 6,
      fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap',
      maxHeight: 200, overflow: 'auto', border: '1px solid #f0f0f0',
    }}>
      {truncated}
    </div>
  )
}

// ---------- 主页面 ----------

export default function TracePage() {
  const { message } = App.useApp()
  const [searchParams] = useSearchParams()
  const [kbs, setKbs] = useState<Kb[]>([])
  const [checkedKbIds, setCheckedKbIds] = useState<number[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [trace, setTrace] = useState<TraceData | null>(null)

  useEffect(() => {
    api.get<Kb[]>('/api/kb').then(setKbs).catch(() => {})
  }, [])

  // 支持 URL 参数：?traceId=xxx&query=xxx&kbIds=xxx
  useEffect(() => {
    const traceId = searchParams.get('traceId')
    const urlQuery = searchParams.get('query')
    const kbIdsStr = searchParams.get('kbIds')
    if (urlQuery) {
      setQuery(urlQuery)
      if (kbIdsStr) {
        // 根据 kb_code 匹配 kb id
        const codes = kbIdsStr.split(',')
        api.get<Kb[]>('/api/kb').then(list => {
          const ids = list.filter(k => codes.includes(k.kbCode)).map(k => k.id)
          setCheckedKbIds(ids)
          // 自动执行 trace
          if (ids.length > 0) {
            setTimeout(() => runTraceWith(urlQuery, ids, list), 300)
          }
        }).catch(() => {})
      }
    }
  }, [searchParams])

  const runTrace = async () => {
    await runTraceWith(query, checkedKbIds, kbs)
  }

  const runTraceWith = async (q: string, ids: number[], kbList: Kb[]) => {
    if (!q.trim() || ids.length === 0) {
      message.warning('请选择知识库并输入查询')
      return
    }
    setLoading(true)
    setTrace(null)
    try {
      const kbCodes = kbList
        .filter(k => ids.includes(k.id))
        .map(k => k.kbCode)
      const data = await api.post<TraceData>('/api/debug/trace', {
        kb_ids: kbCodes,
        query: q.trim(),
        dense_top_k: 20,
        sparse_top_k: 20,
        rerank_top_n: 10,
        score_threshold: 0,
      })
      setTrace(data)
    } catch (e: any) {
      message.error(e.message || 'Trace 请求失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px' }}>
      <Typography.Title level={4} style={{ marginBottom: 4 }}>RAG 全链路追溯</Typography.Title>
      <Text type="secondary">输入查询，观察从 Query → Retrieve → Rerank → Final 每一阶段的中间数据</Text>

      {/* ====== Trace 输入区 ====== */}
      <Card size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <Text strong>知识库：</Text>
            <Select
              mode="multiple"
              style={{ minWidth: 300 }}
              placeholder="选择知识库"
              value={checkedKbIds}
              onChange={(v) => setCheckedKbIds(v)}
              options={kbs.map(k => ({ label: k.name, value: k.id }))}
            />
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <Text strong>Query：</Text>
            <Input
              style={{ flex: 1 }}
              placeholder="输入要追溯的查询，例如：什么是RAG？"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') runTrace() }}
            />
            <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={runTrace}>
              追溯
            </Button>
          </div>
        </Space>
      </Card>

      {/* ====== Trace 结果 ====== */}
      {trace && (
        <>
          {/* Stage 0: Embedding */}
          <Card size="small" title="阶段 0：Query Embedding" style={{ marginTop: 16 }}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="查询">{trace.query}</Descriptions.Item>
              <Descriptions.Item label="向量维度">{trace.embedding_dim}</Descriptions.Item>
              <Descriptions.Item label="稀疏可用">{trace.has_sparse ? '是' : '否（仅稠密）'}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>向量前 8 维预览：</Text>
              <Text code style={{ fontSize: 12 }}>
                [{trace.embedding_preview.map(v => v.toFixed(4)).join(', ')}...]
              </Text>
            </div>
          </Card>

          {/* Stage 1: Vector DB Retrieval */}
          <Card
            size="small" style={{ marginTop: 16 }}
            title={`阶段 1：向量库原始召回 · ${trace.dense_count} 条（Milvus dense search）`}
            extra={<Tag color="blue">Milvus HNSW</Tag>}
          >
            <Table
              dataSource={trace.dense_results}
              rowKey="chunk_id"
              size="small"
              pagination={{ pageSize: 5 }}
              columns={[
                { title: 'Rank', dataIndex: 'rank', width: 50 },
                { title: '来源', dataIndex: 'source_file', width: 120, ellipsis: true },
                { title: '标题路径', render: (_, r) => r.title_path?.join(' / '), width: 150, ellipsis: true },
                {
                  title: 'Score', dataIndex: 'score', width: 150,
                  render: (v: number) => <ScoreBar score={v} label="Milvus IP" />,
                },
                { title: '内容', render: (_, r) => <ContentPreview content={r.content} maxLen={200} /> },
              ]}
            />
          </Card>

          {/* Stage 2: RRF Fusion */}
          <Card
            size="small" style={{ marginTop: 16 }}
            title={`阶段 2：RRF 融合 · ${trace.rrf_count} 条候选`}
            extra={<Tag>dense + sparse → RRF</Tag>}
          >
            <Table
              dataSource={trace.rrf_candidates}
              rowKey="chunk_id"
              size="small"
              pagination={{ pageSize: 5 }}
              columns={[
                { title: '来源', dataIndex: 'source_file', width: 120, ellipsis: true },
                { title: 'Dense Rank', dataIndex: 'dense_rank', width: 90 },
                { title: 'Sparse Rank', dataIndex: 'sparse_rank', width: 90 },
                {
                  title: 'RRF Score', dataIndex: 'rrf_score', width: 150,
                  render: (v: number) => <ScoreBar score={v} max={0.05} label="RRF" />,
                },
                { title: '内容', render: (_, r) => <ContentPreview content={r.content} maxLen={200} /> },
              ]}
            />
          </Card>

          {/* Stage 3: Rerank */}
          <Card
            size="small" style={{ marginTop: 16 }}
            title={`阶段 3：Rerank 精排 · ${trace.rerank_count} 条${trace.rerank_degraded ? '（降级）' : ''}`}
            extra={<Tag color={trace.rerank_degraded ? 'orange' : 'purple'}>SiliconFlow Qwen3-Reranker</Tag>}
          >
            <Table
              dataSource={trace.rerank_candidates}
              rowKey="chunk_id"
              size="small"
              pagination={{ pageSize: 5 }}
              columns={[
                { title: '来源', dataIndex: 'source_file', width: 120, ellipsis: true },
                {
                  title: 'Rerank Score', dataIndex: 'rerank_score', width: 180,
                  render: (v: number) => <ScoreBar score={v} label="Rerank" />,
                },
                {
                  title: 'RRF Score', dataIndex: 'rrf_score', width: 150,
                  render: (v: number) => <ScoreBar score={v} max={0.05} label="RRF(旧)" />,
                },
                { title: '内容', render: (_, r) => <ContentPreview content={r.content} maxLen={200} /> },
              ]}
            />
          </Card>

          {/* Stage 4: Final */}
          <Card
            size="small" style={{ marginTop: 16 }}
            title={`阶段 4：最终输出 · ${trace.final_count} 条${trace.threshold_applied > 0 ? `（阈值 ≥ ${trace.threshold_applied}）` : ''}`}
            extra={<Tag color="green">送给 LLM</Tag>}
          >
            {trace.final_count === 0 ? (
              <Result status="warning" title="无结果" subTitle="所有候选都被阈值过滤，将触发拒答分支" />
            ) : (
              <Table
                dataSource={trace.final_candidates}
                rowKey="chunk_id"
                size="small"
                pagination={{ pageSize: 5 }}
                columns={[
                  { title: '来源', dataIndex: 'source_file', width: 120, ellipsis: true },
                  { title: '标题路径', render: (_, r) => r.title_path?.join(' / '), width: 150, ellipsis: true },
                  {
                    title: 'Rerank Score', dataIndex: 'rerank_score', width: 180,
                    render: (v: number) => <ScoreBar score={v} label="Final" />,
                  },
                  { title: '内容', render: (_, r) => <ContentPreview content={r.content} maxLen={300} /> },
                ]}
              />
            )}
          </Card>

          {/* Stage 5: The actual Prompt sent to LLM */}
          <Card
            size="small" style={{ marginTop: 16 }}
            title={`阶段 5：组装后的 LLM Prompt（${trace.final_count > 0 ? `包含 ${trace.final_count} 条参考资料` : '无参考资料 — 将触发拒答'}）`}
            extra={<Tag color="red">System + User → LLM</Tag>}
          >
            {trace.final_count === 0 ? (
              <Result
                status="warning"
                title="无参考资料，不会发送给 LLM"
                subTitle="所有候选分数均低于阈值，系统会直接返回拒答文案，不消耗 LLM Token"
              />
            ) : (
              <>
                <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
                  <Descriptions.Item label="Token 预算">{trace.final_candidates.length} 条参考资料（按分数从高到低装入，超出预算的低分内容会被丢弃）</Descriptions.Item>
                  <Descriptions.Item label="引用数量">{trace.final_candidates.length} 个 [N] 引用标记</Descriptions.Item>
                </Descriptions>

                {/* System Prompt */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Tag color="blue">System Prompt</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>占位符 {'{contexts}'} 被替换为下方的参考资料块</Text>
                  </div>
                  <pre style={{
                    background: '#1e1e1e', color: '#d4d4d4', padding: 16, borderRadius: 8,
                    fontSize: 13, lineHeight: 1.7, maxHeight: 400, overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}>
{`你是一个严谨的企业知识库助手。基于「参考资料」回答用户问题。

要求：
1. 只依据参考资料回答，资料中没有的内容，明确说"根据现有资料无法回答"，不要编造。
2. 回答中引用资料时，在对应语句末尾标注引用编号，格式 [1] [2]。
3. 回答使用简体中文，结构清晰，必要时使用列表。
4. 不要复述参考资料全文，用自己的话归纳。

【参考资料】
----------------------------------------`}
                    {/* Show each context block */}
                    {trace.final_candidates.map((c, i) => {
                      const source = c.source_file || '未知来源'
                      const page = c.page ? ` 第${c.page}页` : ''
                      const path = c.title_path?.join(' / ') || ''
                      return (
                        <div key={i} style={{ color: '#6a9955' }}>
                          [{i + 1}]（来源：{source}{page}{path ? ` · ${path}` : ''}）
                          <br />
                          <span style={{ color: '#9cdcfe' }}>{c.content.slice(0, 500)}{c.content.length > 500 ? '...' : ''}</span>
                          {'\n'}
                        </div>
                      )
                    })}
{`----------------------------------------`}
                  </pre>
                </div>

                {/* User Message */}
                <div style={{ marginBottom: 8 }}>
                  <Tag color="green">User Message</Tag>
                  <pre style={{
                    background: '#1e1e1e', color: '#ce9178', padding: 16, borderRadius: 8,
                    fontSize: 13, lineHeight: 1.7, maxHeight: 200, overflow: 'auto',
                    whiteSpace: 'pre-wrap', marginTop: 8,
                  }}>
{trace.query}
                  </pre>
                </div>

                {/* Raw JSON payload preview */}
                <div>
                  <Tag>API Payload (发给 DeepSeek 的完整 JSON)</Tag>
                  <pre style={{
                    background: '#fafafa', padding: 12, borderRadius: 8,
                    fontSize: 12, maxHeight: 200, overflow: 'auto', border: '1px solid #f0f0f0',
                  }}>
{JSON.stringify({
  model: 'deepseek-chat',
  messages: [
    { role: 'system', content: '(见上方的 System Prompt，共 ' + trace.system_prompt.length + ' 字符)' },
    { role: 'user', content: trace.query }
  ],
  temperature: 0.1,
  max_tokens: 1024,
  stream: true,
}, null, 2)}
                  </pre>
                </div>
              </>
            )}
          </Card>
        </>
      )}

        </div>
  )
}

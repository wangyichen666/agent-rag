import { DatabaseOutlined, SearchOutlined } from '@ant-design/icons'
import {
  App, Button, Card, Descriptions, Select, Space, Spin, Table, Tag, Typography,
} from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Kb, KbDocument } from '../types'

const { Text, Title } = Typography

// ---------- 存储格式类型 ----------

interface StoredChunkItem {
  chunk_id: string; kb_id: string; doc_id: string
  content: string; dense_dim: number; dense_preview: number[]
  sparse_keys: number; metadata: Record<string, unknown>; parent_id: string
}

interface DocChunksResponse {
  doc_id: string; kb_id: string; chunk_count: number; chunks: StoredChunkItem[]
}

// ---------- 辅助 ----------

function ContentPreview({ content, maxLen = 800 }: { content: string; maxLen?: number }) {
  const truncated = content.length > maxLen ? content.slice(0, maxLen) + '⋯' : content
  return (
    <div style={{
      background: '#fafafa', padding: '8px 12px', borderRadius: 6,
      fontSize: 13, lineHeight: 1.8, whiteSpace: 'pre-wrap',
      maxHeight: 300, overflow: 'auto', border: '1px solid #f0f0f0',
    }}>
      {truncated}
    </div>
  )
}

// ---------- 主页面 ----------

export default function StoragePage() {
  const { message } = App.useApp()

  const [kbs, setKbs] = useState<Kb[]>([])
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null)
  const [docs, setDocs] = useState<KbDocument[]>([])
  const [selectedDocCode, setSelectedDocCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<DocChunksResponse | null>(null)

  // 加载知识库列表
  useEffect(() => {
    api.get<Kb[]>('/api/kb').then(setKbs).catch(() => {})
  }, [])

  // 选中知识库 → 加载文档列表
  useEffect(() => {
    if (selectedKbId === null) {
      setDocs([])
      setSelectedDocCode(null)
      setData(null)
      return
    }
    api.get<KbDocument[]>(`/api/kb/${selectedKbId}/documents`)
      .then(list => {
        setDocs(list)
        setSelectedDocCode(null)
        setData(null)
      })
      .catch(() => {})
  }, [selectedKbId])

  const lookup = async () => {
    if (selectedKbId === null || !selectedDocCode) {
      message.warning('请先选择知识库和文档')
      return
    }
    const kb = kbs.find(k => k.id === selectedKbId)
    if (!kb) return
    setLoading(true)
    setData(null)
    try {
      const result = await api.get<DocChunksResponse>(
        `/api/debug/chunks/${encodeURIComponent(kb.kbCode)}/${encodeURIComponent(selectedDocCode)}`
      )
      setData(result)
    } catch (e: any) {
      message.error(e.message || '查询失败')
    } finally {
      setLoading(false)
    }
  }

  // 知识库选项
  const kbOptions = kbs.map(k => ({
    label: `${k.name} (${k.kbCode})`,
    value: k.id,
  }))

  // 文档选项（按解析状态区分样式）
  const docOptions = docs.map(d => ({
    label: `${d.parseStatus === 'success' ? '✅' : d.parseStatus === 'failed' ? '❌' : '⏳'} ${d.fileName}  [${d.chunkCount ?? 0} chunks]`,
    value: d.docCode,
    disabled: d.parseStatus !== 'success',
  }))

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 16px' }}>
      <Title level={4} style={{ marginBottom: 4 }}>向量库存储格式</Title>
      <Text type="secondary">查看文档在 Milvus 中实际存储的 chunk 结构、metadata 与向量维度</Text>

      <Card size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* Step 1: 选知识库 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong style={{ minWidth: 70 }}>知识库：</Text>
            <Select
              showSearch
              style={{ flex: 1 }}
              placeholder="选择知识库"
              value={selectedKbId}
              onChange={v => setSelectedKbId(v)}
              options={kbOptions}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>

          {/* Step 2: 选文档 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong style={{ minWidth: 70 }}>文档：</Text>
            <Select
              showSearch
              style={{ flex: 1 }}
              placeholder={selectedKbId ? '选择文档（仅显示解析成功的）' : '请先选择知识库'}
              value={selectedDocCode}
              onChange={v => setSelectedDocCode(v)}
              options={docOptions}
              disabled={selectedKbId === null}
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              loading={loading}
              disabled={!selectedDocCode}
              onClick={lookup}
            >
              查看存储格式
            </Button>
          </div>
        </Space>
      </Card>

      {/* 结果 */}
      {data && (
        <>
          <Card size="small" style={{ marginTop: 16 }} title="文档概览">
            <Descriptions size="small" column={4}>
              <Descriptions.Item label="KB ID">{data.kb_id}</Descriptions.Item>
              <Descriptions.Item label="Doc ID">{data.doc_id}</Descriptions.Item>
              <Descriptions.Item label="Chunk 总数">{data.chunk_count}</Descriptions.Item>
              <Descriptions.Item label="向量维度">{data.chunks[0]?.dense_dim ?? '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {data.chunks.length === 0 ? (
            <Card size="small" style={{ marginTop: 16 }}>
              <Text type="secondary">该文档在向量库中没有找到任何 chunk（可能尚未解析成功）</Text>
            </Card>
          ) : (
            data.chunks.map((chunk, idx) => (
              <Card
                key={chunk.chunk_id}
                size="small"
                style={{ marginTop: 12 }}
                title={
                  <Space>
                    <Tag color="blue">Chunk #{idx + 1}</Tag>
                    <Text code>{chunk.chunk_id}</Text>
                  </Space>
                }
                extra={
                  <Space>
                    <Tag>向量: {chunk.dense_dim} 维</Tag>
                    <Tag>{chunk.sparse_keys > 0 ? `稀疏: ${chunk.sparse_keys} keys` : '无稀疏'}</Tag>
                    {chunk.parent_id && <Tag color="orange">parent: {chunk.parent_id}</Tag>}
                  </Space>
                }
              >
                {/* Metadata */}
                <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
                  <Descriptions.Item label="Content Type">
                    {String(chunk.metadata?.content_type ?? 'text')}
                  </Descriptions.Item>
                  <Descriptions.Item label="Source File">
                    {String(chunk.metadata?.source_file ?? '-')}
                  </Descriptions.Item>
                  <Descriptions.Item label="Chunk Index">
                    {String(chunk.metadata?.chunk_index ?? idx)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Title Path" span={2}>
                    {JSON.stringify(chunk.metadata?.title_path ?? [])}
                  </Descriptions.Item>
                  <Descriptions.Item label="Page">
                    {String(chunk.metadata?.page ?? '-')}
                  </Descriptions.Item>
                </Descriptions>

                {/* 内容 */}
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    内容（{chunk.content.length} 字符）：
                  </Text>
                  <ContentPreview content={chunk.content} maxLen={800} />
                </div>

                {/* 完整 metadata JSON */}
                <details>
                  <summary style={{ cursor: 'pointer', color: '#888', fontSize: 13 }}>
                    完整 metadata JSON
                  </summary>
                  <pre style={{
                    background: '#1e1e1e', color: '#9cdcfe', padding: 12, borderRadius: 6,
                    fontSize: 12, maxHeight: 200, overflow: 'auto', marginTop: 8,
                  }}>
                    {JSON.stringify(chunk.metadata, null, 2)}
                  </pre>
                </details>

                {/* 数据流向图 */}
                <details style={{ marginTop: 8 }}>
                  <summary style={{ cursor: 'pointer', color: '#888', fontSize: 13 }}>
                    Milvus 存储结构（字段映射）
                  </summary>
                  <Table
                    size="small"
                    style={{ marginTop: 8 }}
                    pagination={false}
                    dataSource={[
                      { field: 'chunk_id', type: 'VARCHAR(128)', value: chunk.chunk_id, desc: '唯一标识，格式 {doc_id}-{chunk_index}' },
                      { field: 'kb_id', type: 'VARCHAR(64)', value: chunk.kb_id, desc: '知识库 ID（partition key）' },
                      { field: 'doc_id', type: 'VARCHAR(64)', value: chunk.doc_id, desc: '文档 ID' },
                      { field: 'content', type: 'VARCHAR(8192)', value: chunk.content.length > 100 ? chunk.content.slice(0, 100) + '⋯' : chunk.content, desc: 'chunk 文本内容' },
                      { field: 'dense', type: `FLOAT_VECTOR(${chunk.dense_dim})`, value: `[${chunk.dense_dim} 个 float32]`, desc: '稠密向量（SiliconFlow Embedding）' },
                      { field: 'metadata', type: 'JSON', value: JSON.stringify(chunk.metadata), desc: '元信息：source_file, title_path, page, content_type 等' },
                      { field: 'parent_id', type: 'VARCHAR(128)', value: chunk.parent_id || '(空)', desc: '父 chunk ID（parent-child 模式用）' },
                    ]}
                    columns={[
                      { title: '字段', dataIndex: 'field', width: 100, render: (v: string) => <Text code>{v}</Text> },
                      { title: '类型', dataIndex: 'type', width: 150, render: (v: string) => <Tag>{v}</Tag> },
                      { title: '当前值', dataIndex: 'value', ellipsis: true, render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text> },
                      { title: '说明', dataIndex: 'desc', width: 200 },
                    ]}
                  />
                </details>
              </Card>
            ))
          )}
        </>
      )}
    </div>
  )
}

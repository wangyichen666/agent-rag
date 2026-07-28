import { EyeOutlined } from '@ant-design/icons'
import { App, Table, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

const { Title, Text } = Typography

interface RewriteItem {
  messageId: number
  traceId: string
  conversationId: number
  conversationTitle: string
  originalQuery: string
  rewrittenQuery: string
  createdAt: string
}

export default function RewritePage() {
  const { message } = App.useApp()
  const [data, setData] = useState<RewriteItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.get<RewriteItem[]>('/api/messages/rewrites')
      .then(setData)
      .catch(e => message.error(e.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px' }}>
      <Title level={4}>Query 改写记录</Title>
      <Text type="secondary">展示所有经过指代消解改写后的查询，对比原始 query 与改写后 query</Text>

      <Table
        dataSource={data}
        rowKey="messageId"
        loading={loading}
        size="small"
        style={{ marginTop: 16 }}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: '时间', dataIndex: 'createdAt', width: 160, render: (v: string) => v?.replace('T', ' ').substring(0, 19) },
          { title: '对话', dataIndex: 'conversationTitle', width: 160, ellipsis: true },
          {
            title: '原始 Query', dataIndex: 'originalQuery', width: 250, ellipsis: true,
            render: (v: string) => <Text style={{ fontSize: 13 }}>{v}</Text>,
          },
          {
            title: '改写后 Query', dataIndex: 'rewrittenQuery', width: 250, ellipsis: true,
            render: (v: string) => <Text style={{ fontSize: 13, color: '#1677ff' }}><>🔄 {v}</></Text>,
          },
          {
            title: 'Trace', dataIndex: 'traceId', width: 150,
            render: (traceId: string, record: RewriteItem) => (
              traceId ? (
                <Link to={`/trace?traceId=${traceId}&query=${encodeURIComponent(record.rewrittenQuery)}`}>
                  <EyeOutlined /> 查看溯源
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>{traceId}</Text>
                </Link>
              ) : <Text type="secondary">-</Text>
            ),
          },
        ]}
      />
    </div>
  )
}

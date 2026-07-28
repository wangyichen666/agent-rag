import { EyeOutlined, UserOutlined, RobotOutlined } from '@ant-design/icons'
import { App, Card, Collapse, List, Space, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ChatMessage, Conversation } from '../types'

const { Title, Text } = Typography

interface ConvWithMessages extends Conversation {
  messages?: ChatMessage[]
  loading?: boolean
}

export default function HistoryPage() {
  const { message } = App.useApp()
  const [convs, setConvs] = useState<ConvWithMessages[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.get<Conversation[]>('/api/conversations')
      .then(list => setConvs(list.map(c => ({ ...c, messages: undefined, loading: false }))))
      .catch(e => message.error(e.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  const loadMessages = async (conv: ConvWithMessages) => {
    if (conv.messages) {
      // toggle collapse
      setConvs(prev => prev.map(c => c.id === conv.id ? { ...c, messages: undefined } : c))
      return
    }
    setConvs(prev => prev.map(c => c.id === conv.id ? { ...c, loading: true } : c))
    try {
      const msgs = await api.get<ChatMessage[]>(`/api/conversations/${conv.id}/messages`)
      setConvs(prev => prev.map(c => c.id === conv.id ? { ...c, messages: msgs, loading: false } : c))
    } catch (e: any) {
      message.error(e.message || '加载消息失败')
      setConvs(prev => prev.map(c => c.id === conv.id ? { ...c, loading: false } : c))
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '0 16px' }}>
      <Title level={4}>对话记录</Title>
      <Text type="secondary">所有对话及其消息历史，点击展开查看详情，通过 trace_id 可跳转追溯</Text>

      <List
        style={{ marginTop: 16 }}
        loading={loading}
        dataSource={convs}
        renderItem={conv => (
          <Card
            size="small"
            style={{ marginBottom: 12, cursor: 'pointer' }}
            onClick={() => loadMessages(conv)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <Text strong>{conv.title}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {conv.updatedAt?.replace('T', ' ').substring(0, 16)}
                </Text>
              </Space>
              <Tag>{conv.messages ? `${conv.messages.length} 条消息` : '点击展开'}</Tag>
            </div>

            {conv.loading && <Text type="secondary">加载中...</Text>}

            {conv.messages && (
              <div style={{ marginTop: 12, paddingLeft: 16, borderLeft: '2px solid #f0f0f0' }}>
                {conv.messages.map(msg => (
                  <div key={msg.id} style={{ marginBottom: 10 }}>
                    <Space>
                      {msg.role === 'user'
                        ? <Tag color="blue" icon={<UserOutlined />}>User</Tag>
                        : <Tag color="green" icon={<RobotOutlined />}>Assistant</Tag>
                      }
                      <Text style={{ fontSize: 13 }}>
                        {msg.content.length > 150 ? msg.content.slice(0, 150) + '…' : msg.content}
                      </Text>
                    </Space>
                    {msg.traceId && (
                      <div style={{ marginTop: 2, marginLeft: 8 }}>
                        <Link to={`/trace?traceId=${msg.traceId}&query=${encodeURIComponent(msg.content.slice(0, 500))}`}>
                          <EyeOutlined /> trace: {msg.traceId}
                        </Link>
                        {msg.rewrittenQuery && msg.rewrittenQuery !== msg.content && (
                          <Text type="warning" style={{ fontSize: 12, marginLeft: 12 }}>
                            🔄 {msg.rewrittenQuery}
                          </Text>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      />
    </div>
  )
}

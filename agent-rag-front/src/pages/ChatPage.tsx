import { EyeOutlined, PlusOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import { App, Button, Card, Checkbox, Input, List, Space, Spin, Tag, Tooltip, Typography } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'
import { streamChat } from '../api/sse'
import type { ChatMessage, Citation, Conversation, Kb, SseMeta } from '../types'

interface UiMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  noContext?: boolean
  streaming?: boolean
  traceId?: string
  rewrittenQuery?: string
}

const { Text } = Typography

export default function ChatPage() {
  const { message } = App.useApp()
  const [kbs, setKbs] = useState<Kb[]>([])
  const [checkedKbIds, setCheckedKbIds] = useState<number[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConv, setCurrentConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get<Kb[]>('/api/kb').then(setKbs).catch(() => {})
    loadConversations()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages])

  const loadConversations = useCallback(async () => {
    setConversations(await api.get<Conversation[]>('/api/conversations'))
  }, [])

  const openConversation = useCallback(async (conv: Conversation) => {
    setCurrentConv(conv)
    const history = await api.get<ChatMessage[]>(`/api/conversations/${conv.id}/messages`)
    setMessages(
      history.map((m) => ({
        role: m.role,
        content: m.content,
        citations: m.citations ? safeParse(m.citations) : undefined,
        traceId: m.traceId,
        rewrittenQuery: m.rewrittenQuery,
      })),
    )
  }, [])

  const newConversation = useCallback(async () => {
    if (checkedKbIds.length === 0) {
      message.warning('请先勾选至少一个知识库')
      return
    }
    const conv = await api.post<Conversation>('/api/conversations', { kbIds: checkedKbIds })
    setConversations((prev) => [conv, ...prev])
    setCurrentConv(conv)
    setMessages([])
  }, [checkedKbIds, message])

  const send = useCallback(async () => {
    const question = input.trim()
    if (!question || streaming) return
    if (!currentConv) {
      message.warning('请先新建会话')
      return
    }
    setInput('')
    setStreaming(true)
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '', streaming: true },
    ])

    const controller = new AbortController()
    abortRef.current = controller
    let citations: Citation[] = []
    let noContext = false

    try {
      await streamChat(
        '/api/chat/completions',
        { conversationId: currentConv.id, question },
        {
          onMeta: (meta: SseMeta) => {
            citations = meta.citations ?? []
            noContext = meta.no_relevant_context
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              // 对比改写后的 query 是否与原问题不同
              const origQuestion = prev[prev.length - 2]?.content || ''
              const wasRewritten = meta.rewritten_query && meta.rewritten_query !== origQuestion
              return patchLast(prev, {
                citations, noContext,
                traceId: meta.trace_id,
                rewrittenQuery: wasRewritten ? meta.rewritten_query : undefined,
              })
            })
          },
          onToken: (delta) => {
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              return patchLast(prev, { content: last.content + delta })
            })
          },
          onDone: () => {},
          onError: (code, msg) => {
            setMessages((prev) => patchLast(prev, { content: prev[prev.length - 1].content + `\n\n> [${code}] ${msg}` }))
          },
        },
        controller.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages((prev) => patchLast(prev, { content: prev[prev.length - 1].content + `\n\n> 连接中断：${e.message}` }))
      }
    } finally {
      setMessages((prev) => patchLast(prev, { streaming: false }))
      setStreaming(false)
      abortRef.current = null
      loadConversations()
    }
  }, [input, streaming, currentConv, message, loadConversations])

  const stop = () => abortRef.current?.abort()

  return (
    <div className="chat-layout">
      <div className="chat-side">
        <Card
          size="small"
          title="知识库"
          extra={
            <Tooltip title="用勾选的知识库新建会话">
              <Button size="small" type="primary" icon={<PlusOutlined />} onClick={newConversation}>
                新会话
              </Button>
            </Tooltip>
          }
        >
          <Checkbox.Group
            style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
            value={checkedKbIds}
            onChange={(v) => setCheckedKbIds(v as number[])}
            options={kbs.map((k) => ({ label: k.name, value: k.id }))}
          />
        </Card>
        <Card size="small" title="会话" style={{ marginTop: 12, flex: 1 }} styles={{ body: { padding: 0, maxHeight: '50vh', overflow: 'auto' } }}>
          <List
            size="small"
            dataSource={conversations}
            renderItem={(c) => (
              <List.Item
                onClick={() => openConversation(c)}
                style={{
                  cursor: 'pointer',
                  padding: '8px 12px',
                  background: currentConv?.id === c.id ? '#e6f4ff' : undefined,
                }}
              >
                <span className="conv-title">{c.title}</span>
              </List.Item>
            )}
          />
        </Card>
      </div>

      <div className="chat-main">
        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="chat-empty">勾选左侧知识库并点击「新会话」，开始提问</div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg msg-${m.role}`}>
              <div className="msg-bubble">
                {m.role === 'assistant' ? (
                  <>
                    {m.content ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                        {m.content}
                      </ReactMarkdown>
                    ) : (
                      <Spin size="small" />
                    )}
                    {m.streaming && <span className="cursor">▍</span>}
                    {m.citations && m.citations.length > 0 && (
                      <div className="citations">
                        {m.citations.map((c) => (
                          <Tooltip
                            key={c.ref_id}
                            title={`${c.title_path.join(' / ')}${c.page ? ` · 第${c.page}页` : ''} · 相关度 ${(c.score * 100).toFixed(0)}%`}
                          >
                            <Tag className="citation-tag">
                              [{c.ref_id}] {c.source_file}
                              {c.page ? ` P${c.page}` : ''}
                            </Tag>
                          </Tooltip>
                        ))}
                      </div>
                    )}
                    {m.rewrittenQuery && (
                      <div style={{ marginTop: 4, fontSize: 12, color: '#faad14' }}>
                        🔄 已改写：{m.rewrittenQuery}
                      </div>
                    )}
                    {m.traceId && (
                      <div style={{ marginTop: 6, fontSize: 12 }}>
                        <a
                          href={`#/trace?traceId=${m.traceId}&query=${encodeURIComponent(m.content)}`}
                          style={{ color: '#1677ff' }}
                        >
                          <EyeOutlined /> 查看检索链路
                        </a>
                        <Text type="secondary" style={{ marginLeft: 8 }}>trace: {m.traceId}</Text>
                      </div>
                    )}
                  </>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="chat-input">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            autoSize={{ minRows: 1, maxRows: 6 }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
          />
          {streaming ? (
            <Button danger icon={<StopOutlined />} onClick={stop}>
              停止
            </Button>
          ) : (
            <Button type="primary" icon={<SendOutlined />} onClick={send} disabled={!input.trim()}>
              发送
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

function patchLast(list: UiMessage[], patch: Partial<UiMessage>): UiMessage[] {
  if (list.length === 0) return list
  const next = [...list]
  next[next.length - 1] = { ...next[next.length - 1], ...patch }
  return next
}

function safeParse(json: string): Citation[] | undefined {
  try {
    const arr = JSON.parse(json)
    return Array.isArray(arr) ? arr : undefined
  } catch {
    return undefined
  }
}

/** 与 Java 端契约对齐的类型定义。 */

export interface Result<T> {
  code: number
  message: string
  data: T
}

export interface User {
  id: number
  username: string
  nickname: string
}

export interface Kb {
  id: number
  kbCode: string
  name: string
  description?: string
  ownerId: number
  status: number
  createdAt: string
  updatedAt: string
}

export type ParseStatus = 'pending' | 'parsing' | 'success' | 'failed'

export interface KbDocument {
  id: number
  docCode: string
  kbId: number
  fileName: string
  fileType: string
  fileSize: number
  parseStatus: ParseStatus
  chunkCount: number
  errorMsg?: string
  version: number
  createdAt: string
}

export interface Conversation {
  id: number
  userId: number
  kbIds: string
  title: string
  updatedAt: string
}

export interface Citation {
  ref_id: number
  chunk_id: string
  doc_id: string
  source_file: string
  page?: number
  title_path: string[]
  score: number
}

export interface ChatMessage {
  id: number
  traceId?: string
  conversationId: number
  role: 'user' | 'assistant'
  content: string
  rewrittenQuery?: string
  citations?: string
  latencyMs?: number
  feedback?: number
  createdAt: string
}

/** SSE 事件（与 Python/Java 透传协议一致）。 */
export type SseEventName = 'meta' | 'token' | 'done' | 'error'

export interface SseMeta {
  session_id: string
  trace_id: string
  rewritten_query: string
  citations: Citation[]
  no_relevant_context: boolean
}

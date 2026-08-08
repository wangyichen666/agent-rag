export interface SseHandlers {
  onMeta?: (data: any) => void
  onToken?: (delta: string) => void
  onDone?: (data: any) => void
  onError?: (code: string, message: string) => void
}

/**
 * POST + ReadableStream 实现的 SSE 客户端。
 * EventSource 不支持 POST/自定义 Header，故手写解析。
 */
export async function streamChat(
  path: string,
  body: unknown,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(`请求失败 ${resp.status}: ${text.slice(0, 200)}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let currentEvent = 'message'
  let dataLines: string[] = []
  let finished = false

  const dispatch = () => {
    if (dataLines.length === 0) return
    const raw = dataLines.join('\n')
    dataLines = []
    let data: any = null
    try {
      data = JSON.parse(raw)
    } catch {
      return
    }
    switch (currentEvent) {
      case 'meta':
        handlers.onMeta?.(data)
        break
      case 'token':
        if (typeof data?.delta === 'string') handlers.onToken?.(data.delta)
        break
      case 'done':
        handlers.onDone?.(data)
        finished = true
        break
      case 'error':
        handlers.onError?.(data?.code ?? 'UNKNOWN', data?.message ?? '未知错误')
        finished = true
        break
    }
    currentEvent = 'message'
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx).replace(/\r$/, '')
      buffer = buffer.slice(idx + 1)
      if (line === '') {
        dispatch()
      } else if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    // done/error 是 SSE 协议的终止事件：主动关闭读取端，
    // 不依赖服务端/代理关闭连接（Vite 代理可能一直不关）
    if (finished) {
      try {
        await reader.cancel()
      } catch {
        // 已关闭则忽略
      }
      break
    }
  }
  dispatch()
}

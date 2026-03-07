import { create } from 'zustand'

/**
 * Extract the answer text from a partial JSON string being streamed.
 * Gemini outputs: {"answer": "text...", "citations": [...]}
 * We pull out just the answer value for clean display during streaming.
 */
function extractAnswerFromPartialJson(raw) {
  const marker = '"answer"'
  const idx = raw.indexOf(marker)
  if (idx === -1) return null

  const afterKey = raw.indexOf(':', idx + marker.length)
  if (afterKey === -1) return null

  const rest = raw.substring(afterKey + 1).trimStart()
  if (rest.startsWith('null')) return null
  if (!rest.startsWith('"')) return null

  let text = ''
  let i = 1 // skip opening quote
  while (i < rest.length) {
    if (rest[i] === '\\' && i + 1 < rest.length) {
      const next = rest[i + 1]
      if (next === 'n') { text += '\n'; i += 2; continue }
      if (next === 't') { text += '\t'; i += 2; continue }
      if (next === '"') { text += '"'; i += 2; continue }
      if (next === '\\') { text += '\\'; i += 2; continue }
      text += next; i += 2; continue
    }
    if (rest[i] === '"') break
    text += rest[i]
    i++
  }

  return text || null
}

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  conversationId: null,
  streamingContent: '',

  addMessage: (msg) => set(state => ({
    messages: [...state.messages, { ...msg, id: Date.now() }]
  })),

  setLoading: (loading) => set({ isLoading: loading }),
  setStreamingContent: (content) => set({ streamingContent: content }),

  sendQuery: async (query, lawCode = null) => {
    const { addMessage, setLoading, setStreamingContent } = get()
    addMessage({ role: 'user', content: query })
    setLoading(true)
    setStreamingContent('')

    try {
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, language: 'en', law_code: lawCode }),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullText = ''
      let citations = []
      let confidence = 'low'

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const jsonStr = line.slice(5).trim()
          if (!jsonStr) continue

          try {
            const event = JSON.parse(jsonStr)
            if (event.type === 'token') {
              fullText += event.data
              const displayText = extractAnswerFromPartialJson(fullText)
              if (displayText) {
                setStreamingContent(displayText)
              }
            } else if (event.type === 'citations') {
              citations = event.data || []
            } else if (event.type === 'confidence') {
              confidence = event.data || 'low'
            }
          } catch {}
        }
      }

      // Parse the complete JSON to extract final answer + citations
      let answer = fullText
      try {
        let raw = fullText.trim()
        if (raw.startsWith('```')) {
          raw = raw.split('\n', 1)[1]
          raw = raw.substring(0, raw.lastIndexOf('```')).trim()
        }
        const parsed = JSON.parse(raw)
        answer = parsed.answer || null
        if (!citations.length && parsed.citations) {
          citations = parsed.citations
        }
        if (parsed.confidence) {
          confidence = parsed.confidence
        }
      } catch {
        // JSON parse failed — extract answer from partial JSON as fallback
        const extracted = extractAnswerFromPartialJson(fullText)
        if (extracted) {
          answer = extracted
        }
      }

      setStreamingContent('')
      addMessage({
        role: 'assistant',
        content: answer || 'I could not find relevant information in the federal statutes.',
        citations,
        confidence,
      })
    } catch (err) {
      setStreamingContent('')
      addMessage({
        role: 'assistant',
        content: 'An error occurred while processing your query.',
        citations: [],
        confidence: 'low',
      })
    } finally {
      setLoading(false)
    }
  },
}))

import { create } from 'zustand'

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
  appendStreamingContent: (text) => set(s => ({ streamingContent: s.streamingContent + text })),

  sendQuery: async (query, lawCode = null) => {
    const { addMessage, setLoading, setStreamingContent, appendStreamingContent } = get()
    addMessage({ role: 'user', content: query })
    setLoading(true)
    setStreamingContent('')

    try {
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, language: 'en', law_code: lawCode }),
      })

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
              appendStreamingContent(event.data)
            } else if (event.type === 'citations') {
              citations = event.data || []
            } else if (event.type === 'confidence') {
              confidence = event.data || 'low'
            }
          } catch {}
        }
      }

      // Parse the JSON answer from the streamed text
      let answer = fullText
      try {
        const parsed = JSON.parse(fullText)
        answer = parsed.answer || fullText
        if (!citations.length && parsed.citations) {
          citations = parsed.citations
        }
        if (parsed.confidence) {
          confidence = parsed.confidence
        }
      } catch {}

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

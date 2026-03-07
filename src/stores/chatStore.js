import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  conversationId: null,

  addMessage: (msg) => set(state => ({
    messages: [...state.messages, { ...msg, id: Date.now() }]
  })),

  setLoading: (loading) => set({ isLoading: loading }),

  sendQuery: async (query) => {
    const { addMessage, setLoading } = get()
    addMessage({ role: 'user', content: query })
    setLoading(true)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, language: 'en' }),
      })
      const data = await res.json()

      addMessage({
        role: 'assistant',
        content: data.answer || 'I could not find relevant information in the federal statutes.',
        citations: data.citations || [],
        confidence: data.confidence || 'low',
        retrievedSections: data.retrieved_sections || [],
      })
    } catch (err) {
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
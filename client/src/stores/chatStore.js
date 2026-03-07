import { create } from 'zustand'

// Separate audio element just for unlocking browser autoplay policy
const _unlockAudio = new Audio()

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  conversationId: null,
  streamingContent: '',
  isAudioPlaying: false,
  audioPlaybackId: 0,

  addMessage: (msg) => set(state => ({
    messages: [...state.messages, { ...msg, id: Date.now() }]
  })),

  setLoading: (loading) => set({ isLoading: loading }),
  setStreamingContent: (content) => set({ streamingContent: content }),
  appendStreamingContent: (text) => set(s => ({ streamingContent: s.streamingContent + text })),

  stopAudio: () => {
    const { _audio } = get()
    if (_audio) {
      _audio.onended = null
      _audio.onerror = null
      _audio.pause()
    }
    set(state => ({
      _audio: null,
      isAudioPlaying: false,
      audioPlaybackId: state.audioPlaybackId + 1
    }))
  },

  playMessageAudio: async (text) => {
    // Stop anything currently playing first
    get().stopAudio()

    const playId = get().audioPlaybackId

    try {
      set({ isAudioPlaying: true })

      const res = await fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })

      if (!res.ok) throw new Error(`TTS request failed: ${res.status}`)

      // Check if we were stopped while the fetch was in flight
      if (get().audioPlaybackId !== playId) return

      const blob = await res.blob()

      // Check again after reading the blob
      if (get().audioPlaybackId !== playId) return

      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)

      // Store reference so stopAudio can reach it
      set({ _audio: audio })

      audio.onended = () => {
        // Only update state if this is still the active playback
        if (get().audioPlaybackId === playId) {
          set({ isAudioPlaying: false, _audio: null })
        }
        URL.revokeObjectURL(url)
      }

      audio.onerror = () => {
        if (get().audioPlaybackId === playId) {
          set({ isAudioPlaying: false, _audio: null })
        }
        URL.revokeObjectURL(url)
      }

      await audio.play()
    } catch (err) {
      // Only reset state if this playback session is still current
      if (get().audioPlaybackId === playId) {
        console.error('TTS playback error:', err)
        set({ isAudioPlaying: false, _audio: null })
      }
    }
  },

  sendQuery: async (query, lawCode = null) => {
    const { addMessage, setLoading, setStreamingContent, appendStreamingContent } = get()

    // Unlock browser audio context synchronously on user click
    // Uses a separate element so it can't interfere with real playback
    _unlockAudio.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA"
    _unlockAudio.play().catch(() => {})

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
      let streamError = null

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
            } else if (event.detail) {
              // Backend error event (e.g., Gemini rate limit)
              streamError = event.detail
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

      let finalAnswer
      if (streamError) {
        finalAnswer = 'The AI service is temporarily busy. Please wait a moment and try again.'
      } else {
        finalAnswer = answer || 'I could not find relevant information in the federal statutes.'
      }

      addMessage({
        role: 'assistant',
        content: finalAnswer,
        citations,
        confidence,
      })

      // Fire-and-forget TTS — must NOT affect the query pipeline
      try { get().playMessageAudio(finalAnswer) } catch {}
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

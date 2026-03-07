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
    const { addMessage, setLoading, setStreamingContent } = get()

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

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

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
              const displayText = extractAnswerFromPartialJson(fullText)
              if (displayText) {
                setStreamingContent(displayText)
              }
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

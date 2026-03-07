# WORKFLOW-4-VOICE.md — ElevenLabs Voice Integration

> **Owner:** Person 4
> **Depends on:** Person 2 (needs `/api/voice/token` and `/api/voice/llm` working), Person 3 (needs VoiceButton component slot)
> **Delivers to:** The demo (voice is the wow factor)

## Your Job

You own the full bidirectional voice experience: user speaks into mic → ElevenLabs transcribes → your backend runs RAG → Gemini generates answer → ElevenLabs speaks it back. You also own the ElevenLabs Agent configuration and the frontend voice UI components.

## Prerequisites

- ElevenLabs account (free tier: 20 min/month, enough for demo)
- API key from https://elevenlabs.io/app/settings/api-keys
- Agent created in ElevenLabs dashboard (see setup below)
- Person 2's backend running with `/api/voice/token` and `/api/voice/llm` endpoints

## Timeline

### Friday Evening (2-3 hours): ElevenLabs Setup

#### Step 1: Create the Agent

1. Go to https://elevenlabs.io/app/agents
2. Click "Create Agent"
3. Configure:
   - **Name:** StatuteLens Counsel
   - **Agent type:** Custom LLM
   - **Server URL:** `http://localhost:8000/api/voice/llm` (for dev; update to Railway URL for production)
   - **First message:** "Good evening. I'm your legal research assistant for Canadian federal law. What would you like to know?"
   - **Language:** English
   - **Enable interruption handling:** Yes

4. Copy the **Agent ID** — you'll need this for the backend `.env`:
   ```
   ELEVENLABS_AGENT_ID=agent_xxxxxxxxxx
   ```

#### Step 2: Design the Voice

In the Agent settings, under Voice:

1. Click "Voice Design" (or browse Voice Library)
2. If using Voice Design, enter a prompt like:
   > "Confident male voice, age 35-45, deep baritone, measured and deliberate pace, North American accent, professional and articulate, like a senior trial lawyer delivering a closing argument"
3. Generate a few options, pick the one that sounds most authoritative
4. Name it "Counsel" in your library

**Important:** Do NOT attempt to clone any real person's voice. Design an original voice with the *qualities* you want.

#### Step 3: Test the Agent

Use the ElevenLabs dashboard's built-in test widget to verify:
- Agent connects to your backend URL
- Speech is transcribed correctly
- Your backend returns streaming text
- The voice speaks the response

If the backend isn't ready yet, temporarily set the Agent to use a built-in LLM (like GPT-4o-mini) with a legal research system prompt. Switch to Custom LLM once Person 2's endpoint is live.

### Saturday (4-6 hours): Frontend Integration

#### The Voice UI Components

Replace Person 3's `VoiceButton.jsx` stub with the full implementation.

**`src/stores/voiceStore.js`**:
```js
import { create } from 'zustand'

export const useVoiceStore = create((set) => ({
  isActive: false,
  isConnecting: false,
  isSpeaking: false,       // AI is currently speaking
  isListening: false,      // Mic is active, user can speak
  transcript: '',          // Current user transcript
  agentText: '',           // Current agent response text
  error: null,

  setActive: (active) => set({ isActive: active }),
  setConnecting: (connecting) => set({ isConnecting: connecting }),
  setSpeaking: (speaking) => set({ isSpeaking: speaking }),
  setListening: (listening) => set({ isListening: listening }),
  setTranscript: (transcript) => set({ transcript }),
  setAgentText: (text) => set({ agentText: text }),
  appendAgentText: (text) => set(s => ({ agentText: s.agentText + text })),
  setError: (error) => set({ error }),
  reset: () => set({
    isActive: false, isConnecting: false, isSpeaking: false,
    isListening: false, transcript: '', agentText: '', error: null
  }),
}))
```

**`src/components/voice/VoiceSession.jsx`** — the WebSocket manager:
```jsx
import { useRef, useCallback, useEffect } from 'react'
import { useVoiceStore } from '../../stores/voiceStore'
import { useChatStore } from '../../stores/chatStore'

export default function useVoiceSession() {
  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const audioQueueRef = useRef([])
  const isPlayingRef = useRef(false)

  const {
    setActive, setConnecting, setSpeaking, setListening,
    setTranscript, setAgentText, appendAgentText, setError, reset
  } = useVoiceStore()
  const addMessage = useChatStore(s => s.addMessage)

  const startSession = useCallback(async () => {
    try {
      setConnecting(true)
      setError(null)

      // 1. Get signed URL from our backend
      const tokenRes = await fetch('/api/voice/token', { method: 'POST' })
      if (!tokenRes.ok) throw new Error('Failed to get voice token')
      const { signed_url } = await tokenRes.json()

      // 2. Request mic permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      })
      mediaStreamRef.current = stream

      // 3. Set up audio context for recording
      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioContextRef.current.createMediaStreamSource(stream)
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1)

      source.connect(processor)
      processor.connect(audioContextRef.current.destination)

      // 4. Connect WebSocket
      const ws = new WebSocket(signed_url)
      wsRef.current = ws

      ws.onopen = () => {
        setConnecting(false)
        setActive(true)
        setListening(true)
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      }

      ws.onerror = (err) => {
        console.error('WebSocket error:', err)
        setError('Voice connection error')
        stopSession()
      }

      ws.onclose = () => {
        setActive(false)
        setListening(false)
      }

      // 5. Send audio chunks
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return
        const inputData = e.inputBuffer.getChannelData(0)

        // Convert float32 to int16 PCM
        const pcm = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          pcm[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768))
        }

        // Base64 encode
        const bytes = new Uint8Array(pcm.buffer)
        const base64 = btoa(String.fromCharCode(...bytes))

        ws.send(JSON.stringify({
          user_audio_chunk: base64,
        }))
      }

    } catch (err) {
      console.error('Failed to start voice session:', err)
      setError(err.message)
      setConnecting(false)
    }
  }, [])

  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case 'conversation_initiation_metadata':
        // Connection confirmed
        break

      case 'user_transcript':
        const transcript = data.user_transcription_event?.user_transcript || ''
        setTranscript(transcript)
        // Add user message to chat
        if (transcript.trim()) {
          addMessage({ role: 'user', content: transcript })
        }
        break

      case 'agent_response':
        const text = data.agent_response_event?.agent_response || ''
        appendAgentText(text)
        break

      case 'audio':
        // Queue audio chunk for playback
        const audioBase64 = data.audio_event?.audio_base_64
        if (audioBase64) {
          setSpeaking(true)
          playAudioChunk(audioBase64)
        }
        break

      case 'agent_response_correction':
        // Agent corrected its response (rare)
        break

      case 'interruption':
        // User interrupted — stop audio playback
        stopAudioPlayback()
        setSpeaking(false)
        break

      case 'ping':
        // Respond with pong
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'pong',
            event_id: data.ping_event?.event_id,
          }))
        }
        break
    }
  }, [])

  const playAudioChunk = useCallback(async (base64Audio) => {
    try {
      const binaryString = atob(base64Audio)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }

      // Decode as PCM 16kHz mono
      const audioCtx = audioContextRef.current || new AudioContext({ sampleRate: 16000 })
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768
      }

      const buffer = audioCtx.createBuffer(1, float32.length, 16000)
      buffer.getChannelData(0).set(float32)

      const source = audioCtx.createBufferSource()
      source.buffer = buffer
      source.connect(audioCtx.destination)
      source.start()

      source.onended = () => {
        // Check if more audio in queue, otherwise mark as not speaking
        setSpeaking(false)
      }
    } catch (err) {
      console.error('Audio playback error:', err)
    }
  }, [])

  const stopAudioPlayback = useCallback(() => {
    audioQueueRef.current = []
    isPlayingRef.current = false
  }, [])

  const stopSession = useCallback(() => {
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    // Stop mic
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop())
      mediaStreamRef.current = null
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    // Add the final agent response to chat as a message
    const agentText = useVoiceStore.getState().agentText
    if (agentText.trim()) {
      addMessage({
        role: 'assistant',
        content: agentText,
        citations: [], // Voice responses don't have structured citations yet
        confidence: 'medium',
      })
    }

    reset()
  }, [])

  return { startSession, stopSession }
}
```

**`src/components/voice/VoiceButton.jsx`** — the full implementation:
```jsx
import { useVoiceStore } from '../../stores/voiceStore'
import useVoiceSession from './VoiceSession'

export default function VoiceButton() {
  const { isActive, isConnecting, isSpeaking, isListening, transcript, error } = useVoiceStore()
  const { startSession, stopSession } = useVoiceSession()

  const handleClick = () => {
    if (isActive) {
      stopSession()
    } else {
      startSession()
    }
  }

  return (
    <div className="flex items-center gap-3">
      {/* Status indicator */}
      {isActive && (
        <div className="flex items-center gap-2 text-xs">
          {isListening && (
            <span className="flex items-center gap-1" style={{ color: 'var(--green)' }}>
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--green)' }} />
              Listening
            </span>
          )}
          {isSpeaking && (
            <span className="flex items-center gap-1" style={{ color: 'var(--gold)' }}>
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--gold)' }} />
              Speaking
            </span>
          )}
        </div>
      )}

      {/* Transcript preview */}
      {transcript && isActive && (
        <span className="text-xs max-w-48 truncate" style={{ color: 'var(--text-secondary)' }}>
          "{transcript}"
        </span>
      )}

      {/* Main button */}
      <button
        onClick={handleClick}
        disabled={isConnecting}
        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
        style={{
          background: isActive ? 'var(--red)' : 'var(--navy-lighter)',
          color: isActive ? '#fff' : 'var(--text-secondary)',
          border: `1px solid ${isActive ? 'var(--red)' : 'var(--navy-lighter)'}`,
          opacity: isConnecting ? 0.5 : 1,
        }}
      >
        {isConnecting ? (
          '⏳ Connecting...'
        ) : isActive ? (
          '⏹ End Voice'
        ) : (
          '🎤 Voice Mode'
        )}
      </button>

      {error && (
        <span className="text-xs" style={{ color: 'var(--red)' }}>{error}</span>
      )}
    </div>
  )
}
```

**`src/components/voice/AudioVisualizer.jsx`** — optional polish:
```jsx
import { useEffect, useRef } from 'react'
import { useVoiceStore } from '../../stores/voiceStore'

export default function AudioVisualizer() {
  const canvasRef = useRef(null)
  const { isSpeaking, isListening } = useVoiceStore()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const width = canvas.width
    const height = canvas.height

    let animationId
    const draw = () => {
      ctx.clearRect(0, 0, width, height)

      const bars = 20
      const barWidth = width / bars - 2
      const active = isSpeaking || isListening
      const color = isSpeaking ? '#C9A84C' : '#4A9D5B'

      for (let i = 0; i < bars; i++) {
        const barHeight = active
          ? Math.random() * height * 0.8 + height * 0.1
          : height * 0.05
        ctx.fillStyle = color
        ctx.fillRect(
          i * (barWidth + 2),
          (height - barHeight) / 2,
          barWidth,
          barHeight
        )
      }

      animationId = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(animationId)
  }, [isSpeaking, isListening])

  return (
    <canvas
      ref={canvasRef}
      width={200}
      height={40}
      className="rounded"
      style={{ opacity: 0.6 }}
    />
  )
}
```

### Sunday: Integration Testing & Demo Prep

1. **Test the full loop:**
   - Click Voice Mode → mic permission granted → "Listening" indicator
   - Speak a question → see transcript appear
   - Wait for RAG pipeline → hear voice response
   - See text appear in chat pane simultaneously
   - Click End Voice → session closes cleanly

2. **Edge cases to test:**
   - What happens if mic permission is denied? (Show error, don't crash)
   - What happens if ElevenLabs is down? (Graceful fallback message)
   - What happens if user interrupts mid-response? (Audio stops, new query starts)

3. **Demo script:** Prepare 2-3 questions that sound good spoken aloud and produce impressive answers. Practice the timing — the voice response takes 2-3 seconds after speaking.

## Fallback Plan

If full bidirectional voice doesn't work by Sunday morning, fall back to **TTS-only**:

Add a "Read Aloud" button on each assistant message:
```jsx
const handleReadAloud = async (text) => {
  const res = await fetch('https://api.elevenlabs.io/v1/text-to-speech/YOUR_VOICE_ID/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'xi-api-key': 'YOUR_KEY', // Note: this exposes the key client-side. Fine for hackathon.
    },
    body: JSON.stringify({
      text: text,
      model_id: 'eleven_turbo_v2_5',
    }),
  })
  const audioBlob = await res.blob()
  const audioUrl = URL.createObjectURL(audioBlob)
  new Audio(audioUrl).play()
}
```

This is much simpler and still impressive in a demo. Build the full bidirectional first, but have this ready as a backup.

## Files You Own

```
client/src/
  components/voice/
    VoiceButton.jsx         (replace Person 3's stub)
    VoiceSession.jsx        (WebSocket hook)
    AudioVisualizer.jsx     (optional visual)
  stores/
    voiceStore.js
```

Backend files owned by Person 2 but you need to coordinate on:
```
api/routers/voice.py       (Person 2 writes it, you test it)
```

ElevenLabs dashboard config:
```
Agent: StatuteLens Counsel
  - Custom LLM pointing to /api/voice/llm
  - Designed voice (deep, authoritative, measured)
  - English, interruption enabled
```

## Definition of Done

- [ ] ElevenLabs Agent created and configured with custom voice
- [ ] Voice Mode button toggles voice session on/off
- [ ] Mic permission requested and handled (including denial)
- [ ] User speech is transcribed and displayed
- [ ] Transcription is sent through RAG pipeline
- [ ] AI response is spoken in designed voice
- [ ] User can interrupt mid-response
- [ ] Voice conversation appears in chat pane as messages
- [ ] Session closes cleanly (mic released, WebSocket closed)
- [ ] Fallback TTS "Read Aloud" button available if bidirectional fails

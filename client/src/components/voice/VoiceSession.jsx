import { useRef, useCallback } from 'react'
<<<<<<< HEAD
import { useVoiceStore } from '../../stores/voiceStore'
import { useChatStore } from '../../stores/chatStore'

export default function useVoiceSession() {
  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const processorRef = useRef(null)
  const audioQueueRef = useRef([])
  const isPlayingRef = useRef(false)

  const {
    setActive, setConnecting, setSpeaking, setListening,
    setTranscript, appendAgentText, setError, reset
  } = useVoiceStore()
  const addMessage = useChatStore(s => s.addMessage)

  const startSession = useCallback(async () => {
    try {
      setConnecting(true)
      setError(null)

      const tokenRes = await fetch('/api/voice/token', { method: 'POST' })
      if (!tokenRes.ok) throw new Error('Failed to get voice token')
      const { signed_url } = await tokenRes.json()

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        }
      })
      mediaStreamRef.current = stream

      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
      const source = audioContextRef.current.createMediaStreamSource(stream)
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      source.connect(processor)
      processor.connect(audioContextRef.current.destination)

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

      ws.onerror = () => {
        setError('Voice connection error. Please try again.')
        stopSession()
      }

      ws.onclose = () => {
        setActive(false)
        setListening(false)
      }

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return
        const inputData = e.inputBuffer.getChannelData(0)

        const pcm = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          pcm[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768))
        }

        const bytes = new Uint8Array(pcm.buffer)
        let binary = ''
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i])
        }
        const base64 = btoa(binary)

        ws.send(JSON.stringify({ user_audio_chunk: base64 }))
      }

    } catch (err) {
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied.')
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found.')
      } else {
        setError(err.message)
      }
      setConnecting(false)
    }
  }, [])

  const handleWebSocketMessage = useCallback((data) => {
    switch (data.type) {
      case 'conversation_initiation_metadata':
        break

      case 'user_transcript': {
        const transcript = data.user_transcription_event?.user_transcript || ''
        setTranscript(transcript)
        if (transcript.trim()) {
          addMessage({ role: 'user', content: transcript })
        }
        break
      }

      case 'agent_response': {
        const text = data.agent_response_event?.agent_response || ''
        appendAgentText(text)
        break
      }

      case 'audio': {
        const audioBase64 = data.audio_event?.audio_base_64
        if (audioBase64) {
          setSpeaking(true)
          queueAudioChunk(audioBase64)
        }
        break
      }

      case 'interruption':
        stopAudioPlayback()
        setSpeaking(false)
        break

      case 'ping':
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'pong',
            event_id: data.ping_event?.event_id,
          }))
        }
        break
    }
  }, [])

  const queueAudioChunk = useCallback((base64Audio) => {
    audioQueueRef.current.push(base64Audio)
    if (!isPlayingRef.current) {
      playNextChunk()
    }
  }, [])

  const playNextChunk = useCallback(async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false
      setSpeaking(false)
      return
    }

    isPlayingRef.current = true
    const base64Audio = audioQueueRef.current.shift()

    try {
      const binaryString = atob(base64Audio)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }

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

      source.onended = () => playNextChunk()
    } catch (err) {
      playNextChunk()
    }
  }, [])

  const stopAudioPlayback = useCallback(() => {
    audioQueueRef.current = []
    isPlayingRef.current = false
  }, [])

  const stopSession = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop())
      mediaStreamRef.current = null
    }

    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    stopAudioPlayback()

    const agentText = useVoiceStore.getState().agentText
    if (agentText.trim()) {
      addMessage({
        role: 'assistant',
        content: agentText,
        citations: [],
        confidence: 'medium',
      })
    }

    reset()
  }, [])

  return { startSession, stopSession }
=======
import { Conversation } from '@11labs/client'
import { useVoiceStore } from '../../stores/voiceStore'

/**
 * useVoiceSession — manages the ElevenLabs Conversational AI session
 * using the official @11labs/client SDK.
 *
 * Flow:
 *   1. Fetch a signed WebSocket URL from our backend (/api/voice/token)
 *   2. SDK handles mic, WebSocket/WebRTC, STT, and TTS automatically
 *   3. We just listen for events (transcript, agent response, mode changes)
 */
export default function useVoiceSession() {
    const conversationRef = useRef(null)

    const {
        setActive, setConnecting, setSpeaking, setListening,
        setTranscript, setAgentText, appendAgentText, setError, reset
    } = useVoiceStore()

    // ------- Start a new voice session -------
    const startSession = useCallback(async () => {
        try {
            setConnecting(true)
            setError(null)

            // 1. Request mic permission
            await navigator.mediaDevices.getUserMedia({ audio: true })

            // 2. Get signed URL from our backend
            const tokenRes = await fetch('/api/voice/token', { method: 'POST' })
            if (!tokenRes.ok) throw new Error('Failed to get voice token')
            const { signed_url } = await tokenRes.json()

            // 3. Start conversation using the official ElevenLabs SDK
            const conversation = await Conversation.startSession({
                signedUrl: signed_url,

                onConnect: () => {
                    setConnecting(false)
                    setActive(true)
                    setListening(true)
                },

                onDisconnect: () => {
                    setActive(false)
                    setListening(false)
                    setSpeaking(false)
                },

                onError: (error) => {
                    console.error('ElevenLabs error:', error)
                    setError(error?.message || 'Voice connection error')
                },

                onModeChange: (mode) => {
                    if (mode.mode === 'speaking') {
                        setSpeaking(true)
                        setListening(false)
                    } else if (mode.mode === 'listening') {
                        setSpeaking(false)
                        setListening(true)
                    }
                },

                onMessage: (message) => {
                    // Handle user transcripts
                    if (message.type === 'user_transcript') {
                        const transcript = message.user_transcription_event?.user_transcript || ''
                        if (transcript.trim()) {
                            setTranscript(transcript)
                        }
                    }

                    // Handle agent responses
                    if (message.type === 'agent_response') {
                        const text = message.agent_response_event?.agent_response || ''
                        if (text) {
                            appendAgentText(text)
                        }
                    }
                },
            })

            conversationRef.current = conversation

        } catch (err) {
            console.error('Failed to start voice session:', err)

            if (err.name === 'NotAllowedError') {
                setError('Microphone permission denied. Please allow mic access and try again.')
            } else if (err.name === 'NotFoundError') {
                setError('No microphone found. Please connect a mic and try again.')
            } else {
                setError(err.message)
            }

            setConnecting(false)
        }
    }, [])

    // ------- Stop the voice session -------
    const stopSession = useCallback(async () => {
        if (conversationRef.current) {
            await conversationRef.current.endSession()
            conversationRef.current = null
        }
        reset()
    }, [])

    return { startSession, stopSession }
>>>>>>> origin/elevenlabs
}

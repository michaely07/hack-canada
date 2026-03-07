import { useRef, useCallback } from 'react'
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
}

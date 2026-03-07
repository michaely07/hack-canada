import { useVoiceStore } from '../../stores/voiceStore'
import useVoiceSession from './VoiceSession'
import AudioVisualizer from './AudioVisualizer'

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
      {isActive && <AudioVisualizer />}

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

      {transcript && isActive && (
        <span className="text-xs max-w-48 truncate" style={{ color: 'var(--text-secondary)' }}>
          "{transcript}"
        </span>
      )}

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
        {isConnecting ? 'Connecting...' : isActive ? 'End Voice' : 'Voice Mode'}
      </button>

      {error && (
        <span className="text-xs" style={{ color: 'var(--red)' }}>{error}</span>
      )}
    </div>
  )
}

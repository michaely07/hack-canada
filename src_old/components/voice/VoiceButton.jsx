export default function VoiceButton() {
  return (
    <button
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors"
      style={{ background: 'var(--navy-lighter)', color: 'var(--text-secondary)' }}
    >
      🎤 Voice Mode
    </button>
  )
}
import { useChatStore } from '../../stores/chatStore'

export default function StatusBar() {
  const messages = useChatStore(s => s.messages)
  const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')

  const confidence = lastAssistant?.confidence
  const citationCount = lastAssistant?.citations?.length || 0

  const confidenceColor = {
    high: 'var(--gold)',
    medium: '#D4A843',
    low: 'var(--red)',
  }[confidence] || 'var(--text-secondary)'

  return (
    <div className="flex items-center justify-between px-6 py-2 text-xs"
         style={{
           borderTop: '1px solid rgba(201, 168, 76, 0.12)',
           color: 'var(--text-secondary)',
           fontFamily: "'Lora', serif",
         }}>
      <div className="flex items-center gap-4">
        {confidence && (
          <span>
            Confidence: <span style={{ color: confidenceColor }} className="font-medium uppercase">{confidence}</span>
          </span>
        )}
        {citationCount > 0 && (
          <span>{citationCount} section{citationCount !== 1 ? 's' : ''} cited</span>
        )}
      </div>
      <span style={{ color: 'var(--gold-dim)', letterSpacing: '0.03em' }}>
        Powered by Gemini + Canadian Federal Law XML
      </span>
    </div>
  )
}

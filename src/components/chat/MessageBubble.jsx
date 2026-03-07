import { useState } from 'react'
import { motion } from 'framer-motion'
import CitationBadge from './CitationBadge'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className="max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed"
        style={{
          background: isUser ? 'var(--navy-lighter)' : 'var(--navy-light)',
          borderLeft: isUser ? 'none' : '3px solid var(--gold-dim)',
        }}
      >
        {/* Render answer text with citation badges inline */}
        <div className="whitespace-pre-wrap">
          {isUser ? message.content : renderWithCitations(message.content, message.citations)}
        </div>

        {/* Citation list below message */}
        {!isUser && (
          <div className="flex items-center justify-between mt-3 pt-2 border-t"
               style={{ borderColor: 'var(--navy-lighter)' }}>
            <div className="flex flex-wrap gap-1.5 overflow-hidden">
              {message.citations?.map((c, i) => (
                <CitationBadge key={i} citation={c} />
              ))}
            </div>
            
            <button
              onClick={handleCopy}
              className="ml-4 shrink-0 flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors"
              style={{ 
                color: copied ? 'var(--green)' : 'var(--text-secondary)',
                background: 'rgba(255,255,255,0.05)'
              }}
            >
              {copied ? '✓ Copied' : '⧉ Cite This'}
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function renderWithCitations(text, citations) {
  if (!text || !citations?.length) return text

  // Replace [Section X] patterns with clickable badges
  // This is a simple regex approach; refine as needed
  const parts = text.split(/(\[Section [^\]]+\])/g)
  return parts.map((part, i) => {
    const match = part.match(/\[Section ([^\]]+)\]/)
    if (match) {
      const label = match[1]
      const citation = citations.find(c => c.label === label || part.includes(c.label))
      if (citation) {
        return <CitationBadge key={i} citation={citation} inline />
      }
    }
    return <span key={i}>{part}</span>
  })
}
import React, { useState, useEffect } from 'react'
import { useChatStore } from '../../stores/chatStore'

export default function QueryInput() {
  const [input, setInput] = useState('')
  const [lawCode, setLawCode] = useState('')
  const [laws, setLaws] = useState([])
  const [focused, setFocused] = useState(false)
  const { sendQuery, isLoading } = useChatStore()

  useEffect(() => {
    fetch('/api/laws')
      .then(r => r.json())
      .then(data => setLaws(data))
      .catch(() => { })

    // Close dropdown when clicking outside
    const handleClickOutside = () => setIsDropdownOpen(false)
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendQuery(input.trim(), lawCode || null)
    setInput('')
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4"
      style={{
        borderTop: '1px solid rgba(201, 168, 76, 0.12)',
        background: 'linear-gradient(to top, rgba(10, 22, 40, 0.5), transparent)',
      }}
    >
      <div className="flex gap-2">
        <select
          value={lawCode}
          onChange={e => setLawCode(e.target.value)}
          className="px-3 py-2.5 rounded-lg text-sm outline-none"
          style={{
            background: 'var(--navy-light)',
            color: 'var(--text-primary)',
            border: '1px solid rgba(201, 168, 76, 0.15)',
            minWidth: '140px',
            fontFamily: "'Lora', serif",
          }}
        >
          <option value="">All Laws</option>
          {laws.map(law => (
            <option key={law.code} value={law.code}>
              {law.code} - {law.short_title_en}
            </option>
          ))}
        </select>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question or enter a query..."
          disabled={isLoading}
          className="flex-1 px-4 py-2.5 rounded-lg text-sm outline-none transition-all duration-200"
          style={{
            background: 'var(--navy-light)',
            color: 'var(--text-primary)',
            border: focused ? '1px solid var(--gold-dim)' : '1px solid rgba(201, 168, 76, 0.15)',
            boxShadow: focused ? '0 0 12px rgba(201, 168, 76, 0.1)' : 'none',
            fontFamily: "'Lora', serif",
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="search-btn px-5 py-2.5 rounded-lg text-sm"
        >
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </div>
    </form>
  )
}

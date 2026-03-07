# WORKFLOW-3-FRONTEND.md — React Frontend (Split-Screen UI)

> **Owner:** Person 3
> **Depends on:** Person 2 (needs API endpoints by Saturday morning, can mock until then)
> **Delivers to:** Everyone (this is what the judges see)

## Your Job

You own the React frontend: the split-screen layout, the chat pane with citation badges, the auditor pane that shows source XML, the legal graph tab, and the overall visual design. This is the demo layer — what you build is what wins or loses the hackathon.

## Prerequisites

- Node.js 20+
- Person 2's API running on `localhost:8000` (or mock data until it's ready)

## Design Direction

**Aesthetic: "Digital Law Library"** — Dark, authoritative, precise. Not the typical light-mode SaaS dashboard.

- **Background:** Deep navy `#0A1628`
- **Text:** Off-white `#E8E4DC` on dark, dark navy on light surfaces
- **Accent (citations, interactive):** Warm gold `#C9A84C`
- **Warning/low confidence:** Red `#C23B22`
- **Typography:** `Crimson Pro` (serif) for headings, `IBM Plex Sans` for body, `IBM Plex Mono` for section numbers and legal refs
- **Layout:** 40% chat / 60% auditor on desktop. Tabbed on mobile.

Add Google Fonts to `index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
```

## Timeline

### Friday Evening (3-4 hours)

#### Hour 1: Scaffold

```bash
npm create vite@latest client -- --template react
cd client
npm install zustand @reactflow/core framer-motion
npm install -D tailwindcss @tailwindcss/vite
```

**`vite.config.js`**:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

**`src/index.css`**:
```css
@import "tailwindcss";

:root {
  --navy: #0A1628;
  --navy-light: #132240;
  --navy-lighter: #1A3058;
  --gold: #C9A84C;
  --gold-dim: #9A7D3A;
  --text-primary: #E8E4DC;
  --text-secondary: #9BA4B5;
  --red: #C23B22;
  --green: #4A9D5B;
}

body {
  background: var(--navy);
  color: var(--text-primary);
  font-family: 'IBM Plex Sans', sans-serif;
}

h1, h2, h3, h4 { font-family: 'Crimson Pro', serif; }
code, .mono { font-family: 'IBM Plex Mono', monospace; }
```

#### Hours 2-4: Core Layout

**`src/App.jsx`**:
```jsx
import { useState } from 'react'
import AppShell from './components/layout/AppShell'

export default function App() {
  return <AppShell />
}
```

**`src/components/layout/AppShell.jsx`**:
```jsx
import { useState } from 'react'
import ChatPane from '../chat/ChatPane'
import AuditorPane from '../auditor/AuditorPane'
import StatusBar from './StatusBar'
import VoiceButton from '../voice/VoiceButton'

export default function AppShell() {
  const [activeTab, setActiveTab] = useState('source') // 'source' | 'graph'

  return (
    <div className="h-screen flex flex-col" style={{ background: 'var(--navy)' }}>
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b"
              style={{ borderColor: 'var(--navy-lighter)' }}>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold" style={{ color: 'var(--gold)' }}>
            StatuteLens
          </h1>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Canadian Federal Law
          </span>
        </div>
        <VoiceButton />
      </header>

      {/* Main split-screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chat (40%) */}
        <div className="w-2/5 border-r flex flex-col"
             style={{ borderColor: 'var(--navy-lighter)' }}>
          <ChatPane />
        </div>

        {/* Right: Auditor (60%) */}
        <div className="w-3/5 flex flex-col">
          {/* Tabs */}
          <div className="flex border-b" style={{ borderColor: 'var(--navy-lighter)' }}>
            <button
              onClick={() => setActiveTab('source')}
              className={`px-4 py-2 text-sm font-medium ${
                activeTab === 'source' ? 'border-b-2' : ''
              }`}
              style={{
                borderColor: activeTab === 'source' ? 'var(--gold)' : 'transparent',
                color: activeTab === 'source' ? 'var(--gold)' : 'var(--text-secondary)',
              }}
            >
              Source Viewer
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              className={`px-4 py-2 text-sm font-medium ${
                activeTab === 'graph' ? 'border-b-2' : ''
              }`}
              style={{
                borderColor: activeTab === 'graph' ? 'var(--gold)' : 'transparent',
                color: activeTab === 'graph' ? 'var(--gold)' : 'var(--text-secondary)',
              }}
            >
              Legal Graph
            </button>
          </div>

          <AuditorPane activeTab={activeTab} />
        </div>
      </div>

      {/* Status bar */}
      <StatusBar />
    </div>
  )
}
```

**`src/stores/chatStore.js`**:
```js
import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  conversationId: null,

  addMessage: (msg) => set(state => ({
    messages: [...state.messages, { ...msg, id: Date.now() }]
  })),

  setLoading: (loading) => set({ isLoading: loading }),

  sendQuery: async (query) => {
    const { addMessage, setLoading } = get()
    addMessage({ role: 'user', content: query })
    setLoading(true)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, language: 'en' }),
      })
      const data = await res.json()

      addMessage({
        role: 'assistant',
        content: data.answer || 'I could not find relevant information in the federal statutes.',
        citations: data.citations || [],
        confidence: data.confidence || 'low',
        retrievedSections: data.retrieved_sections || [],
      })
    } catch (err) {
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
```

**`src/stores/auditorStore.js`**:
```js
import { create } from 'zustand'

export const useAuditorStore = create((set) => ({
  activeSection: null,     // { lims_id, label, content_text, content_xml, law_code, law_title }
  isLoading: false,

  loadSection: async (limsId) => {
    set({ isLoading: true })
    try {
      const res = await fetch(`/api/sections/${limsId}`)
      const data = await res.json()
      set({ activeSection: data, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
    }
  },

  clearSection: () => set({ activeSection: null }),
}))
```

### Saturday (8-10 hours) — Core Components

**`src/components/chat/ChatPane.jsx`**:
```jsx
import { useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import MessageBubble from './MessageBubble'
import QueryInput from './QueryInput'

export default function ChatPane() {
  const { messages, isLoading } = useChatStore()

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <h2 className="text-2xl mb-2" style={{ color: 'var(--gold)' }}>
                Ask a legal question
              </h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                Answers are grounded in Canadian federal statutes
              </p>
            </div>
          </div>
        )}
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex gap-1 px-4 py-2">
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--gold)', animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--gold)', animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--gold)', animationDelay: '300ms' }} />
          </div>
        )}
      </div>

      {/* Input */}
      <QueryInput />
    </div>
  )
}
```

**`src/components/chat/MessageBubble.jsx`**:
```jsx
import CitationBadge from './CitationBadge'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
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
        {message.citations?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3 pt-2 border-t"
               style={{ borderColor: 'var(--navy-lighter)' }}>
            {message.citations.map((c, i) => (
              <CitationBadge key={i} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
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
```

**`src/components/chat/CitationBadge.jsx`**:
```jsx
import { useAuditorStore } from '../../stores/auditorStore'

export default function CitationBadge({ citation, inline = false }) {
  const loadSection = useAuditorStore(s => s.loadSection)

  const handleClick = () => {
    if (citation.lims_id) {
      loadSection(citation.lims_id)
    }
  }

  return (
    <button
      onClick={handleClick}
      className={`
        ${inline ? 'inline-flex mx-0.5' : 'flex'}
        items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
        transition-all duration-150 hover:scale-105
        ${citation.hallucinated ? 'opacity-50 line-through' : 'cursor-pointer'}
      `}
      style={{
        background: citation.hallucinated ? 'var(--red)' : 'rgba(201, 168, 76, 0.15)',
        color: citation.hallucinated ? '#fff' : 'var(--gold)',
        border: `1px solid ${citation.hallucinated ? 'var(--red)' : 'var(--gold-dim)'}`,
      }}
      title={citation.hallucinated ? 'Citation not found in retrieved sources' : `Click to view source`}
    >
      <span className="mono">Sec. {citation.label}</span>
      <span style={{ color: 'var(--text-secondary)' }}>{citation.law_code}</span>
    </button>
  )
}
```

**`src/components/chat/QueryInput.jsx`**:
```jsx
import { useState } from 'react'
import { useChatStore } from '../../stores/chatStore'

export default function QueryInput() {
  const [input, setInput] = useState('')
  const { sendQuery, isLoading } = useChatStore()

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendQuery(input.trim())
    setInput('')
  }

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t" style={{ borderColor: 'var(--navy-lighter)' }}>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about Canadian federal law..."
          disabled={isLoading}
          className="flex-1 px-4 py-2.5 rounded-lg text-sm outline-none"
          style={{
            background: 'var(--navy-lighter)',
            color: 'var(--text-primary)',
            border: '1px solid var(--navy-lighter)',
          }}
          onFocus={e => e.target.style.borderColor = 'var(--gold-dim)'}
          onBlur={e => e.target.style.borderColor = 'var(--navy-lighter)'}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          style={{
            background: input.trim() ? 'var(--gold)' : 'var(--navy-lighter)',
            color: input.trim() ? 'var(--navy)' : 'var(--text-secondary)',
          }}
        >
          Search
        </button>
      </div>
    </form>
  )
}
```

**`src/components/auditor/AuditorPane.jsx`**:
```jsx
import { useAuditorStore } from '../../stores/auditorStore'
import SectionViewer from './SectionViewer'
import LegalGraph from './LegalGraph'

export default function AuditorPane({ activeTab }) {
  const { activeSection, isLoading } = useAuditorStore()

  if (activeTab === 'graph') {
    return <LegalGraph />
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p style={{ color: 'var(--text-secondary)' }}>Loading section...</p>
      </div>
    )
  }

  if (!activeSection) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <p className="text-lg mb-2" style={{ color: 'var(--text-secondary)' }}>
            Click a citation badge to view the source
          </p>
          <p className="text-sm" style={{ color: 'var(--text-secondary)', opacity: 0.6 }}>
            The exact statutory text used by the AI will appear here
          </p>
        </div>
      </div>
    )
  }

  return <SectionViewer section={activeSection} />
}
```

**`src/components/auditor/SectionViewer.jsx`**:
```jsx
export default function SectionViewer({ section }) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      {/* Law title */}
      <div className="mb-4 pb-3 border-b" style={{ borderColor: 'var(--navy-lighter)' }}>
        <p className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--gold-dim)' }}>
          {section.law_code}
        </p>
        <h2 className="text-lg font-semibold">{section.law_title}</h2>
      </div>

      {/* Section header */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="mono text-lg font-medium" style={{ color: 'var(--gold)' }}>
            Section {section.label}
          </span>
          {section.marginal_note && (
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              — {section.marginal_note}
            </span>
          )}
        </div>
      </div>

      {/* Section text */}
      <div className="text-sm leading-relaxed whitespace-pre-wrap mb-6"
           style={{ color: 'var(--text-primary)' }}>
        {section.content_text}
      </div>

      {/* Raw XML toggle */}
      {section.content_xml && (
        <details className="mt-4">
          <summary className="text-xs cursor-pointer"
                   style={{ color: 'var(--gold-dim)' }}>
            View Raw XML
          </summary>
          <pre className="mt-2 p-3 rounded text-xs overflow-x-auto mono"
               style={{ background: 'var(--navy)', color: 'var(--text-secondary)' }}>
            {section.content_xml}
          </pre>
        </details>
      )}
    </div>
  )
}
```

**`src/components/auditor/LegalGraph.jsx`** — placeholder, build if time allows:
```jsx
export default function LegalGraph() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <p style={{ color: 'var(--text-secondary)' }}>
        Legal Graph — shows how statutes reference each other
      </p>
    </div>
  )
}
```

**`src/components/layout/StatusBar.jsx`**:
```jsx
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
    <div className="flex items-center justify-between px-6 py-2 text-xs border-t"
         style={{ borderColor: 'var(--navy-lighter)', color: 'var(--text-secondary)' }}>
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
      <span>Powered by Gemini + Canadian Federal Law XML</span>
    </div>
  )
}
```

**`src/components/voice/VoiceButton.jsx`** — stub for Person 4:
```jsx
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
```

### Sunday: Polish

- Add framer-motion animations (message fade-in, citation badge hover effects)
- Build the Legal Graph tab with React Flow if time allows
- Test the full flow: type question → see answer with citations → click badge → auditor shows source
- Responsive behavior for demo (make sure it looks good on the projector resolution)
- Add the "Cite This" copy button under assistant messages

## Files You Own

```
client/
  src/
    components/
      layout/    (AppShell, StatusBar)
      chat/      (ChatPane, MessageBubble, CitationBadge, QueryInput)
      auditor/   (AuditorPane, SectionViewer, LegalGraph)
      voice/     (VoiceButton — stub for Person 4)
    stores/
      chatStore.js
      auditorStore.js
    api/
      client.js
    App.jsx
    index.css
  vite.config.js
  tailwind.config.js
  index.html
  package.json
```

## Definition of Done

- [ ] Split-screen layout renders (40/60 split)
- [ ] User can type a question and see an AI response
- [ ] Citation badges appear in AI responses
- [ ] Clicking a citation badge loads the section in the auditor pane
- [ ] Auditor pane shows section text, law title, marginal note
- [ ] Raw XML toggle works in auditor pane
- [ ] Status bar shows confidence level and citation count
- [ ] Hallucinated citations display with red warning styling
- [ ] Dark theme with gold accents looks professional
- [ ] Empty states are handled (no messages, no section selected)

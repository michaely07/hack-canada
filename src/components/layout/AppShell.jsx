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
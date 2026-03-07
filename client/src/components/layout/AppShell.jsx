import { useState } from 'react'
import ChatPane from '../chat/ChatPane'
import AuditorPane from '../auditor/AuditorPane'
import StatusBar from './StatusBar'
import { useChatStore } from '../../stores/chatStore'

function MapleLeaf() {
  return (
    <img
      className="maple-leaf"
      src="https://static.vecteezy.com/system/resources/previews/034/169/496/non_2x/canadian-maple-leaf-isolated-on-a-transparent-background-free-png.png"
      alt="Canadian Maple Leaf"
      width="32"
      height="32"
      style={{ objectFit: 'contain' }}
    />
  )
}

export default function AppShell() {
  const [activeTab, setActiveTab] = useState('source')
  const { isAudioPlaying, stopAudio } = useChatStore()

  return (
    <div className="h-screen flex flex-col" style={{ background: 'var(--navy)' }}>
      <header className="flex items-center justify-between px-6 py-3 border-b"
              style={{ borderColor: 'rgba(201, 168, 76, 0.12)' }}>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-wide" style={{ color: 'var(--gold)' }}>
              StatuteLens
            </h1>
            <span className="text-sm" style={{ color: 'var(--text-secondary)', fontFamily: "'Lora', serif" }}>
              Canadian Federal Law
            </span>
          </div>
          
          {isAudioPlaying && (
            <button
              onClick={stopAudio}
              className="px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-2"
              style={{
                background: 'rgba(255, 100, 100, 0.1)',
                color: '#ff6b6b',
                border: '1px solid rgba(255, 100, 100, 0.2)'
              }}
            >
              <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#ff6b6b' }} />
              Stop Voice
            </button>
          )}
        </div>

        <MapleLeaf />
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Chat panel — 60% */}
        <div className="flex flex-col" style={{ width: '60%' }}>
          <ChatPane />
        </div>

        {/* Glowing divider */}
        <div className="panel-divider" />

        {/* Source viewer — 40% */}
        <div className="flex flex-col" style={{ width: '40%' }}>
          <div className="flex border-b" style={{ borderColor: 'rgba(201, 168, 76, 0.12)' }}>
            <button
              onClick={() => setActiveTab('source')}
              className={`tab-button px-5 py-2.5 text-sm font-medium ${activeTab === 'source' ? 'active' : ''}`}
              style={{
                color: activeTab === 'source' ? 'var(--gold)' : 'var(--text-secondary)',
                borderBottom: 'none',
              }}
            >
              Source Viewer
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              className={`tab-button px-5 py-2.5 text-sm font-medium ${activeTab === 'graph' ? 'active' : ''}`}
              style={{
                color: activeTab === 'graph' ? 'var(--gold)' : 'var(--text-secondary)',
                borderBottom: 'none',
              }}
            >
              Legal Graph
            </button>
          </div>
          <AuditorPane activeTab={activeTab} />
        </div>
      </div>

      <StatusBar />
    </div>
  )
}

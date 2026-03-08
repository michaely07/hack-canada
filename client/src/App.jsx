import React, { Component, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import AppShell from './components/layout/AppShell'
import LandingPage from './components/layout/LandingPage'
import { useChatStore } from './stores/chatStore'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', color: '#ff6b6b', background: '#faf5f3', minHeight: '100vh', fontFamily: 'monospace' }}>
          <h1>React Error</h1>
          <pre style={{ whiteSpace: 'pre-wrap', marginTop: '1rem' }}>
            {this.state.error?.message}
            {'\n\n'}
            {this.state.error?.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [showLanding, setShowLanding] = useState(true)
  const sendQuery = useChatStore(s => s.sendQuery)

  const handleEnter = (query) => {
    setShowLanding(false)
    if (query) {
      setTimeout(() => sendQuery(query), 600)
    }
  }

  return (
    <ErrorBoundary>
      <AnimatePresence mode="wait">
        {showLanding ? (
          <motion.div
            key="landing"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.4, ease: 'easeInOut' }}
          >
            <LandingPage onEnter={handleEnter} />
          </motion.div>
        ) : (
          <motion.div
            key="app"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="h-screen"
          >
            <AppShell />
          </motion.div>
        )}
      </AnimatePresence>
    </ErrorBoundary>
  )
}

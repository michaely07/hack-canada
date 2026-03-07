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
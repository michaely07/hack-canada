import React, { useMemo } from 'react'
import ReactFlow, { Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'
import { useChatStore } from '../../stores/chatStore'

const nodeStyle = {
  background: 'var(--navy-light)',
  color: 'var(--gold)',
  border: '1px solid var(--gold-dim)',
  borderRadius: '6px',
  padding: '12px 16px',
  fontSize: '12px',
  fontFamily: '"IBM Plex Mono", monospace',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
  maxWidth: '220px'
}

const questionNodeStyle = {
  background: 'var(--navy)',
  color: 'var(--text-primary)',
  border: '1px solid var(--navy-lighter)',
  borderRadius: '8px',
  padding: '12px 16px',
  fontSize: '13px',
  fontFamily: '"Lora", serif',
  boxShadow: '0 4px 12px -1px rgba(0, 0, 0, 0.7)',
  maxWidth: '260px'
}

export default function LegalGraph() {
  const messages = useChatStore(state => state.messages)

  const { nodes, edges } = useMemo(() => {
    const newNodes = []
    const newEdges = []
    const sectionNodes = new Set() // keep track of unique sections so laws don't duplicate
    let yOffset = 50

    messages.forEach((msg, idx) => {
      if (msg.role === 'user') {
        const qId = `q-${idx}`

        let xOffset = 50
        const spacing = 220
        const nextMsg = messages[idx + 1]

        // Calculate center for question node based on how many laws were retrieved
        const lawCount = nextMsg?.retrieved_sections?.length || 1
        const blockWidth = (lawCount - 1) * spacing
        const questionCenterX = 50 + (blockWidth / 2)

        newNodes.push({
          id: qId,
          position: { x: questionCenterX, y: yOffset },
          data: { label: `Q: ${msg.content}` },
          style: questionNodeStyle
        })

        if (nextMsg && nextMsg.role === 'assistant' && nextMsg.retrieved_sections) {
          yOffset += 140

          nextMsg.retrieved_sections.forEach((sec, sIdx) => {
            const sId = `s-${sec.lims_id}`

            // Only add node if it doesn't exist yet
            if (!sectionNodes.has(sId)) {
              sectionNodes.add(sId)
              newNodes.push({
                id: sId,
                position: { x: xOffset, y: yOffset },
                data: { label: `Sec ${sec.label} - ${sec.law_code}` },
                style: nodeStyle
              })
            }

            // Draw line connecting Question to Statute
            newEdges.push({
              id: `e-${qId}-${sId}`,
              source: qId,
              target: sId,
              animated: true,
              style: {
                stroke: 'var(--gold)',
                strokeWidth: sec.score > 0.8 ? 2 : 1, // Thicker line for higher retrieval confidence
                opacity: 0.6
              }
            })

            xOffset += spacing
          })
        }
        yOffset += 160
      }
    })

    // Fallback if empty
    if (newNodes.length === 0) {
      newNodes.push({
        id: 'empty',
        position: { x: 250, y: 150 },
        data: { label: 'Start chatting to build the Live RAG graph' },
        style: questionNodeStyle
      })
    }

    return { nodes: newNodes, edges: newEdges }
  }, [messages])

  return (
    <div className="flex-1 w-full relative" style={{ background: 'var(--navy)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.5}
      >
        <Background color="#132240" gap={16} />
        <Controls />
      </ReactFlow>
      <div className="absolute top-4 left-4 p-3 rounded-lg border text-xs bg-opacity-80 backdrop-blur z-10"
        style={{ background: 'var(--navy-light)', borderColor: 'var(--navy-lighter)', color: 'var(--text-secondary)' }}>
        <p className="mb-1 uppercase tracking-wider text-[10px]" style={{ color: 'var(--gold-dim)' }}>Live RAG Graph</p>
        <p>Retrieval-Augmented Generation Trace</p>
      </div>
    </div>
  )
}

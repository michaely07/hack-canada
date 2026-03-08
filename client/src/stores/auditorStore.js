import { create } from 'zustand'

export const useAuditorStore = create((set) => ({
  activeSection: null,
  isLoading: false,
  activeTab: 'source',

  analysisText: null,
  isAnalyzing: false,

  setActiveTab: (tab) => set({ activeTab: tab }),

  loadSection: async (limsId) => {
    set({ isLoading: true, activeTab: 'source', analysisText: null })
    try {
      const res = await fetch(`/api/sections/${limsId}`)
      const data = await res.json()
      set({ activeSection: data, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
    }
  },

  analyzeSection: async (limsId) => {
    set({ isAnalyzing: true, analysisText: null })
    try {
      const res = await fetch('/api/query/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lims_id: limsId })
      })
      const data = await res.json()
      set({ analysisText: data.summary, isAnalyzing: false })
    } catch (err) {
      set({ analysisText: 'Failed to analyze section. Please try again.', isAnalyzing: false })
    }
  },

  clearSection: () => set({ activeSection: null, analysisText: null }),
}))

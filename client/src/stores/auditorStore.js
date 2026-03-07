import { create } from 'zustand'

export const useAuditorStore = create((set) => ({
  activeSection: null,
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

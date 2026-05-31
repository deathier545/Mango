import { useEffect } from 'react'
import type { AppView } from '../types/ui'

const VIEW_BY_DIGIT: Record<string, AppView> = {
  '1': 'mango',
  '2': 'chat',
  '3': 'conversation',
  '4': 'metrics',
  '5': 'smart',
  '6': 'settings',
}

export function useKeyboardShortcuts(
  onView: (view: AppView) => void,
  onSendChat: () => void,
  activeView: AppView,
  onCommandPalette?: () => void,
  onMangoView?: () => void,
  onSaveSettings?: () => void,
) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if ((e.key === 's' || e.key === 'S') && activeView === 'settings' && onSaveSettings) {
          e.preventDefault()
          onSaveSettings()
          return
        }
        if ((e.key === 'k' || e.key === 'K') && onCommandPalette) {
          e.preventDefault()
          onCommandPalette()
          return
        }
        const digit = e.key
        if (digit in VIEW_BY_DIGIT) {
          e.preventDefault()
          if (digit === '1' && onMangoView) onMangoView()
          else onView(VIEW_BY_DIGIT[digit])
          return
        }
      }
      if (activeView === 'chat' && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        onSendChat()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onView, onSendChat, activeView, onCommandPalette, onMangoView, onSaveSettings])
}

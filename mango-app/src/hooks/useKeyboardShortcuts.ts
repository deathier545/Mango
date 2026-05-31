import { useEffect, type RefObject } from 'react'
import type { AppZone } from '../types/ui'

const ZONE_BY_DIGIT: Record<string, AppZone> = {
  '1': 'command',
  '2': 'intelligence',
  '3': 'diagnostics',
  '4': 'config',
}

export function useKeyboardShortcuts(
  onZone: (zone: AppZone) => void,
  onSendChat: () => void,
  activeZone: AppZone,
  onCommandPalette?: () => void,
  onToggleContext?: () => void,
  onOpenSettings?: () => void,
  commandInputRef?: RefObject<HTMLTextAreaElement | null>,
) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if ((e.key === ',' || e.key === 's' || e.key === 'S') && onOpenSettings) {
          e.preventDefault()
          onOpenSettings()
          return
        }
        if ((e.key === 'k' || e.key === 'K') && onCommandPalette) {
          e.preventDefault()
          onCommandPalette()
          return
        }
        if (e.key === '\\' && onToggleContext) {
          e.preventDefault()
          onToggleContext()
          return
        }
        const digit = e.key
        if (digit in ZONE_BY_DIGIT) {
          e.preventDefault()
          onZone(ZONE_BY_DIGIT[digit])
          return
        }
        if (e.key === 'Enter') {
          const inputFocused =
            document.activeElement === commandInputRef?.current ||
            document.activeElement?.classList.contains('commandInput')
          if (inputFocused) {
            e.preventDefault()
            onSendChat()
          }
          return
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onZone, onSendChat, activeZone, onCommandPalette, onToggleContext, onOpenSettings, commandInputRef])
}

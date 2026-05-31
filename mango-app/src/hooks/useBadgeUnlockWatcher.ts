import { useEffect, useRef } from 'react'
import type { SmartSnapshot } from '../types/ui'
import type { NotifyFn } from './useMangoBridge'

const POLL_MS = 30_000

export function useBadgeUnlockWatcher(running: boolean, notify: NotifyFn) {
  const unlockedRef = useRef<Set<string>>(new Set())
  const initializedRef = useRef(false)

  useEffect(() => {
    if (!running || !window.mango) return

    const poll = async () => {
      try {
        const r = await window.mango!.smartSnapshot()
        if (!r.ok || !r.data) return
        const snap = r.data as SmartSnapshot
        const badges = snap?.badges?.badges ?? []
        const nowUnlocked = new Set(badges.filter((b) => b.unlocked).map((b) => b.id))

        if (initializedRef.current) {
          for (const badge of badges) {
            if (badge.unlocked && !unlockedRef.current.has(badge.id)) {
              notify(`Badge unlocked: ${badge.icon} ${badge.title}`, 'success')
            }
          }
        } else {
          initializedRef.current = true
        }

        unlockedRef.current = nowUnlocked
      } catch {
        // snapshot unavailable — skip
      }
    }

    void poll()
    const id = window.setInterval(poll, POLL_MS)
    return () => window.clearInterval(id)
  }, [running, notify])

  useEffect(() => {
    if (!running) {
      initializedRef.current = false
      unlockedRef.current = new Set()
    }
  }, [running])
}

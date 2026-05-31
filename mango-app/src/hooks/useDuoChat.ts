import { useCallback, useEffect, useRef, useState } from 'react'

import type { DuoLine } from '../components/DuoScene'
import { duoUnavailableMessage, hasDuoBridge } from '../lib/mango-bridge'
import { unwrapIpcData } from '../lib/ipc-unpack'
import type { OrbState } from '../types/ui'

type NotifyFn = (message: string, kind?: 'info' | 'success' | 'error') => void

const MAX_DUO_TOPIC = 300

function phaseToOrbState(phase: string): OrbState {
  if (phase === 'thinking') return 'thinking'
  if (phase === 'speaking') return 'speaking'
  if (phase === 'idle') return 'idle'
  return 'listening'
}

function mapDuoLines(raw: Array<{ speaker?: string; text?: string }> | undefined): DuoLine[] {
  if (!raw?.length) return []
  return raw.map((line) => ({
    speaker: line.speaker === 'amber' ? 'amber' : 'mango',
    text: String(line.text || ''),
  }))
}

export function useDuoChat(notify: NotifyFn, duoBlocked: boolean) {
  const [duoMode, setDuoMode] = useState(false)
  const [duoTopic, setDuoTopic] = useState('')
  const [duoRounds, setDuoRounds] = useState(2)
  const [duoSpeak, setDuoSpeak] = useState(true)
  const [duoRunning, setDuoRunning] = useState(false)
  const [duoLines, setDuoLines] = useState<DuoLine[]>([])
  const [mangoDuoState, setMangoDuoState] = useState<OrbState>('idle')
  const [amberDuoState, setAmberDuoState] = useState<OrbState>('idle')
  const duoRunningRef = useRef(false)
  const mangoAudioRef = useRef(0)
  const amberAudioRef = useRef(0)

  const setTopicLimited = useCallback((topic: string) => {
    setDuoTopic(topic.slice(0, MAX_DUO_TOPIC))
  }, [])

  useEffect(() => {
    if (!window.mango) return
    const unsub = window.mango.onEvent((event) => {
      if (event.type !== 'parsed') return
      const p = event.payload
      if (p.kind === 'duo_done') {
        if (p.lines?.length) setDuoLines(mapDuoLines(p.lines))
        return
      }
      if (p.kind !== 'duo_phase') return
      const speaker = p.speaker === 'amber' ? 'amber' : 'mango'
      const phase = phaseToOrbState(p.phase)
      if (speaker === 'amber') {
        setAmberDuoState(phase)
        amberAudioRef.current = phase === 'speaking' ? 0.35 : 0
      } else {
        setMangoDuoState(phase)
        mangoAudioRef.current = phase === 'speaking' ? 0.35 : 0
      }
      if (p.text && p.phase === 'speaking') {
        setDuoLines((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.speaker === speaker && last.text === p.text) return prev
          return [...prev, { speaker, text: p.text }]
        })
      }
    })
    return () => {
      if (unsub) unsub()
    }
  }, [])

  const resetDuoVisual = useCallback(() => {
    setMangoDuoState('idle')
    setAmberDuoState('idle')
    mangoAudioRef.current = 0
    amberAudioRef.current = 0
  }, [])

  const startDuo = useCallback(async () => {
    if (!hasDuoBridge()) {
      notify(duoUnavailableMessage(), 'error')
      return
    }
    if (duoBlocked) {
      notify('Duo works best when Mango is idle. Wait for voice playback to finish or stop Mango.', 'error')
      return
    }
    const topic = duoTopic.trim()
    if (!topic) {
      notify('Enter a topic for Mango and Amber to discuss.', 'error')
      return
    }
    duoRunningRef.current = true
    setDuoRunning(true)
    setDuoLines([])
    setMangoDuoState('thinking')
    setAmberDuoState('idle')
    notify('Starting duo conversation…', 'info')
    try {
      const result = unwrapIpcData(
        await window.mango.runDuo({ topic, rounds: duoRounds, speak: duoSpeak }),
      )
      if (!result.ok) {
        throw new Error(result.error || 'Duo conversation failed.')
      }
      if (result.lines?.length) {
        setDuoLines(mapDuoLines(result.lines))
      }
      notify('Duo conversation finished.', 'success')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (!msg.toLowerCase().includes('cancel')) {
        notify(`Duo conversation failed: ${msg}`, 'error')
      } else {
        notify('Duo conversation stopped.', 'info')
      }
    } finally {
      duoRunningRef.current = false
      setDuoRunning(false)
      resetDuoVisual()
    }
  }, [duoTopic, duoRounds, duoSpeak, duoBlocked, notify, resetDuoVisual])

  const stopDuo = useCallback(async () => {
    if (!window.mango?.stopDuo) return
    try {
      unwrapIpcData(await window.mango.stopDuo())
    } catch {
      // process exit will settle startDuo promise
    }
  }, [])

  const enterDuoMode = useCallback(() => {
    setDuoMode(true)
    resetDuoVisual()
  }, [resetDuoVisual])

  const exitDuoMode = useCallback(async () => {
    if (duoRunningRef.current) {
      await stopDuo()
    }
    setDuoMode(false)
    setDuoLines([])
    resetDuoVisual()
  }, [resetDuoVisual, stopDuo])

  return {
    duoMode,
    duoAvailable: hasDuoBridge(),
    duoTopic,
    setDuoTopic: setTopicLimited,
    duoRounds,
    setDuoRounds,
    duoSpeak,
    setDuoSpeak,
    duoRunning,
    duoLines,
    mangoDuoState,
    amberDuoState,
    mangoAudioRef,
    amberAudioRef,
    duoBlocked,
    startDuo,
    stopDuo,
    enterDuoMode,
    exitDuoMode,
  }
}

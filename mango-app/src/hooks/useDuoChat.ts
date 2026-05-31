import { useCallback, useEffect, useRef, useState } from 'react'

import type { DuoLine } from '../components/DuoScene'
import { unwrapIpcData } from '../lib/ipc-unpack'
import type { OrbState } from '../types/ui'

type NotifyFn = (message: string, kind?: 'info' | 'success' | 'error') => void

function phaseToOrbState(phase: string): OrbState {
  if (phase === 'thinking') return 'thinking'
  if (phase === 'speaking') return 'speaking'
  if (phase === 'idle') return 'idle'
  return 'listening'
}

export function useDuoChat(notify: NotifyFn) {
  const [duoMode, setDuoMode] = useState(false)
  const [duoTopic, setDuoTopic] = useState('')
  const [duoRounds, setDuoRounds] = useState(2)
  const [duoRunning, setDuoRunning] = useState(false)
  const [duoLines, setDuoLines] = useState<DuoLine[]>([])
  const [mangoDuoState, setMangoDuoState] = useState<OrbState>('idle')
  const [amberDuoState, setAmberDuoState] = useState<OrbState>('idle')
  const duoRunningRef = useRef(false)
  const mangoAudioRef = useRef(0)
  const amberAudioRef = useRef(0)

  useEffect(() => {
    if (!window.mango) return
    const unsub = window.mango.onEvent((event) => {
      if (event.type !== 'parsed') return
      const p = event.payload
      if (p.kind !== 'duo_phase') return
      const speaker = p.speaker === 'amber' ? 'amber' : 'mango'
      const phase = phaseToOrbState(p.phase)
      if (speaker === 'amber') {
        setAmberDuoState(phase)
        if (phase === 'speaking') amberAudioRef.current = 0.35
      } else {
        setMangoDuoState(phase)
        if (phase === 'speaking') mangoAudioRef.current = 0.35
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

  const startDuo = useCallback(async () => {
    if (!window.mango?.runDuo) {
      notify('Duo mode requires the Electron app.', 'error')
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
        await window.mango.runDuo({ topic, rounds: duoRounds, speak: true }),
      )
      if (!result.ok) {
        throw new Error(result.error || 'Duo conversation failed.')
      }
      if (result.lines?.length) {
        setDuoLines(
          result.lines.map((line) => ({
            speaker: line.speaker === 'amber' ? 'amber' : 'mango',
            text: line.text,
          })),
        )
      }
      notify('Duo conversation finished.', 'success')
    } catch (err) {
      notify(`Duo conversation failed: ${err instanceof Error ? err.message : String(err)}`, 'error')
    } finally {
      duoRunningRef.current = false
      setDuoRunning(false)
      setMangoDuoState('idle')
      setAmberDuoState('idle')
      mangoAudioRef.current = 0
      amberAudioRef.current = 0
    }
  }, [duoTopic, duoRounds, notify])

  const enterDuoMode = useCallback(() => {
    setDuoMode(true)
    setMangoDuoState('idle')
    setAmberDuoState('idle')
  }, [])

  const exitDuoMode = useCallback(() => {
    if (duoRunningRef.current) return
    setDuoMode(false)
    setDuoLines([])
    setMangoDuoState('idle')
    setAmberDuoState('idle')
  }, [])

  return {
    duoMode,
    duoTopic,
    setDuoTopic,
    duoRounds,
    setDuoRounds,
    duoRunning,
    duoLines,
    mangoDuoState,
    amberDuoState,
    mangoAudioRef,
    amberAudioRef,
    startDuo,
    enterDuoMode,
    exitDuoMode,
  }
}

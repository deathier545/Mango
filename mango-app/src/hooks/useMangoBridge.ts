import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { unwrapIpcData } from '../lib/ipc-unpack'
import type { MangoEvent } from '../types/events'
import type {
  LogEntry,
  MangoSettings,
  MangoStatus,
  MapTarget,
  TimelineItem,
  ToolEvent,
  TurnMetrics,
  UsageSample,
} from '../types/ui'

const DEFAULT_SETTINGS: MangoSettings = {
  wakeEnabled: true,
  strictTools: false,
  powershellConfirmation: true,
  safeMode: false,
  groqModel: 'llama-3.3-70b-versatile',
  edgeVoice: 'en-US-GuyNeural',
  edgeRate: '+0%',
  edgePitch: '+0Hz',
  edgeVolume: '+0%',
  interruptProfile: 'normal',
  promptTokenRatePer1k: 0,
  completionTokenRatePer1k: 0,
}

export type NotifyFn = (message: string, kind?: 'info' | 'success' | 'error') => void

export type MangoBridgeGlobeHandlers = {
  onGlobeOpen?: () => void
  onGlobeVisibleChange?: (visible: boolean) => void
}

export function useMangoBridge(notify: NotifyFn, globeHandlers?: MangoBridgeGlobeHandlers) {
  const [status, setStatus] = useState<MangoStatus>({ running: false, pid: null, startedAt: null })
  const [savedSettings, setSavedSettings] = useState<MangoSettings>(DEFAULT_SETTINGS)
  const [settings, setSettings] = useState<MangoSettings>(DEFAULT_SETTINGS)
  const [assistantState, setAssistantState] = useState('idle')
  const [transcript, setTranscript] = useState('')
  const [reply, setReply] = useState('')
  const [globeVisible, setGlobeVisible] = useState(false)
  const [globeUrl, setGlobeUrl] = useState('')
  const [globeLabel, setGlobeLabel] = useState('Map')
  const [mapTarget, setMapTarget] = useState<MapTarget>({ lat: 41.9295, lng: -88.7504, zoom: 11 })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [conversationTimeline, setConversationTimeline] = useState<TimelineItem[]>([])
  const [chatTimeline, setChatTimeline] = useState<TimelineItem[]>([])
  const [turnMetrics, setTurnMetrics] = useState<TurnMetrics | null>(null)
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([])
  const [usageSamples, setUsageSamples] = useState<UsageSample[]>([])
  const [lastErrorAt, setLastErrorAt] = useState<number | null>(null)
  const [startPending, setStartPending] = useState(false)
  const [startProgress, setStartProgress] = useState('')

  const chatSeqRef = useRef(0)
  const pendingChatRequestRef = useRef<string | null>(null)
  const audioLevelRef = useRef(0)
  const statusRunningRef = useRef(status.running)
  const speakingResetTimer = useRef<number | null>(null)
  const startPendingRef = useRef(false)
  const noiseHintAtRef = useRef(0)

  const armSpeakingReset = useCallback((delayMs: number) => {
    if (speakingResetTimer.current) {
      window.clearTimeout(speakingResetTimer.current)
      speakingResetTimer.current = null
    }
    speakingResetTimer.current = window.setTimeout(() => {
      setAssistantState(statusRunningRef.current ? 'listening' : 'idle')
      speakingResetTimer.current = null
    }, delayMs)
  }, [])

  useEffect(() => {
    if (!window.mango) {
      notify('Mango desktop bridge not detected. Open this UI from Electron.', 'error')
      return
    }
    let unsub: (() => void) | null = null
    void window.mango.getStatus().then((r) => setStatus(unwrapIpcData(r))).catch((err) => notify(`Failed to load Mango status: ${String(err)}`, 'error'))
    void window.mango
      .getRecentLogs()
      .then((items) => setLogs(unwrapIpcData(items).slice(-200)))
      .catch((err) => notify(`Failed to load logs: ${String(err)}`, 'error'))
    void window.mango
      .getSettings()
      .then((s) => {
        const loaded = unwrapIpcData(s)
        setSettings(loaded)
        setSavedSettings(loaded)
      })
      .catch((err) => notify(`Failed to load settings: ${String(err)}`, 'error'))

    unsub = window.mango.onEvent((event: MangoEvent) => {
      if (event.type === 'status') {
        setStatus(event.payload)
        if (event.payload.running && startPendingRef.current) {
          setStartPending(false)
          startPendingRef.current = false
        }
      }
      if (event.type === 'log') {
        setLogs((prev) => [...prev.slice(-199), event.payload])
        const kind = String(event.payload.kind || '').toLowerCase()
        const line = String(event.payload.line || '').toLowerCase()
        if (kind.includes('error') || line.includes('traceback') || line.includes('exception')) {
          setLastErrorAt(Date.now())
        }
        if (
          startPendingRef.current &&
          (line.includes('mango ready') ||
            line.includes('wake hands-free') ||
            line.includes('always-listen') ||
            line.includes('listening — hold'))
        ) {
          setStartPending(false)
          startPendingRef.current = false
          setStartProgress('')
        } else if (startPendingRef.current) {
          if (line.includes('starting mango with')) setStartProgress('Launching process')
          else if (line.includes('wake')) setStartProgress('Initializing wake pipeline')
          else if (line.includes('starting transcription')) setStartProgress('Audio pipeline ready')
        }
      }
      if (event.type === 'parsed') {
        const p = event.payload
        if (p.kind === 'state') {
          setAssistantState(p.state)
          if (p.state === 'speaking') {
            armSpeakingReset(22000)
          } else if (speakingResetTimer.current) {
            window.clearTimeout(speakingResetTimer.current)
            speakingResetTimer.current = null
          }
          if (
            startPendingRef.current &&
            (p.state === 'listening' || p.state === 'idle') &&
            p.text.toLowerCase().includes('mango ready')
          ) {
            setStartPending(false)
            startPendingRef.current = false
          }
        }
        if (p.kind === 'audio_level') {
          const level = Number.isFinite(p.level) ? p.level : 0
          audioLevelRef.current = Math.max(0, Math.min(1, level))
          if (audioLevelRef.current > 0.02) {
            setAssistantState('speaking')
            armSpeakingReset(1200 + Math.round(audioLevelRef.current * 3200))
          }
        }
        if (p.kind === 'globe') {
          setGlobeUrl(p.url || '')
          setGlobeLabel(p.label || 'Map')
          let lat = Number.isFinite(p.lat) ? (p.lat as number) : null
          let lng = Number.isFinite(p.lng) ? (p.lng as number) : null
          let zoom: number | null =
            Number.isFinite(p.zoom) && p.zoom != null ? Math.max(2, Math.min(19, p.zoom)) : null
          try {
            const u = new URL(p.url)
            const mlat = Number(u.searchParams.get('mlat'))
            const mlon = Number(u.searchParams.get('mlon'))
            if (lat == null && Number.isFinite(mlat)) lat = mlat
            if (lng == null && Number.isFinite(mlon)) lng = mlon
            const hashMatch = u.hash.match(/map=(\d+)\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/)
            if (hashMatch) {
              const z = Number(hashMatch[1])
              const hashLat = Number(hashMatch[2])
              const hashLng = Number(hashMatch[3])
              if (Number.isFinite(z)) zoom = Math.max(2, Math.min(19, z))
              if (lat == null && Number.isFinite(hashLat)) lat = hashLat
              if (lng == null && Number.isFinite(hashLng)) lng = hashLng
            }
          } catch {
            // ignore malformed URL
          }
          if (lat != null && lng != null) {
            setMapTarget((prev) => ({ lat, lng, zoom: zoom ?? prev.zoom }))
          }
          setGlobeVisible(true)
          globeHandlers?.onGlobeOpen?.()
        }
        if (p.kind === 'globe_state') {
          setGlobeVisible(Boolean(p.visible))
          globeHandlers?.onGlobeVisibleChange?.(Boolean(p.visible))
        }
        if (p.kind === 'transcript') {
          setTranscript(p.text)
          chatSeqRef.current += 1
          setConversationTimeline((prev) => [
            ...prev.slice(-49),
            {
              id: `voice-${Date.now()}`,
              seq: chatSeqRef.current,
              ts: Date.now(),
              role: 'user',
              text: p.text,
            },
          ])
        }
        if (p.kind === 'reply') {
          setReply(p.text)
          chatSeqRef.current += 1
          setConversationTimeline((prev) => [
            ...prev.slice(-49),
            {
              id: `voice-${Date.now()}`,
              seq: chatSeqRef.current,
              ts: Date.now(),
              role: 'assistant',
              text: p.text,
            },
          ])
        }
        if (p.kind === 'metric_turn') {
          setTurnMetrics((prev) => ({
            correlationId: p.correlationId,
            source: p.source || prev?.source || '',
            sttS: p.sttS ?? prev?.sttS ?? null,
            llmS: p.llmS ?? prev?.llmS ?? null,
            ttsS: p.ttsS ?? prev?.ttsS ?? null,
          }))
        }
        if (p.kind === 'metric_tool') {
          setToolEvents((prev) => [
            ...prev.slice(-39),
            {
              ts: Date.now(),
              correlationId: p.correlationId,
              tool: p.tool,
              risk: p.risk,
              event: p.event,
              ok: p.ok,
              durationMs: p.durationMs ?? null,
            },
          ])
        }
        if (p.kind === 'metric_usage') {
          setUsageSamples((prev) => [
            ...prev.slice(-59),
            {
              ts: Date.now(),
              promptTokens: p.promptTokens,
              completionTokens: p.completionTokens,
              totalTokens: p.totalTokens,
              totalTime: p.totalTime,
              queueTime: p.queueTime,
            },
          ])
        }
        if (p.kind === 'noise_guidance') {
          const now = Date.now()
          if (now - noiseHintAtRef.current > 60_000) {
            noiseHintAtRef.current = now
            notify(
              'Noisy room detected. For cleaner interruptions, try push-to-talk or set Interrupt profile to strict.',
              'info',
            )
          }
        }
      }
    })
    return () => {
      if (unsub) unsub()
      if (speakingResetTimer.current) window.clearTimeout(speakingResetTimer.current)
    }
  }, [armSpeakingReset, notify, globeHandlers])

  useEffect(() => {
    if (!startPending) return
    const t = window.setTimeout(() => {
      setStartPending(false)
      setStartProgress('')
    }, 90_000)
    return () => window.clearTimeout(t)
  }, [startPending])

  useEffect(() => {
    if (!lastErrorAt) return
    const t = window.setTimeout(() => setLastErrorAt(null), 6000)
    return () => window.clearTimeout(t)
  }, [lastErrorAt])

  useEffect(() => {
    statusRunningRef.current = status.running
  }, [status.running])

  const startMango = useCallback(async () => {
    if (!window.mango) return
    try {
      startPendingRef.current = true
      setStartPending(true)
      setStartProgress('Starting Mango')
      const next = unwrapIpcData(await window.mango.start(settings))
      setStatus(next)
      if (next.running) {
        startPendingRef.current = false
        setStartPending(false)
        setStartProgress('')
      }
      notify('Mango started.', 'success')
    } catch (err) {
      startPendingRef.current = false
      setStartPending(false)
      setStartProgress('')
      notify(`Failed to start Mango: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [settings, notify])

  const stopMango = useCallback(async () => {
    if (!window.mango) return
    try {
      const next = unwrapIpcData(await window.mango.stop())
      setStatus(next)
      setAssistantState('stopped')
      startPendingRef.current = false
      setStartPending(false)
      setStartProgress('')
      notify('Mango stopped.', 'info')
    } catch (err) {
      notify(`Failed to stop Mango: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [notify])

  const restartMango = useCallback(async () => {
    if (!window.mango) return
    try {
      startPendingRef.current = true
      setStartPending(true)
      setStartProgress('Restarting Mango')
      notify('Restarting Mango…', 'info')
      if (window.mango.stopDuo) {
        try {
          unwrapIpcData(await window.mango.stopDuo())
        } catch {
          // ignore duo stop errors during restart
        }
      }
      unwrapIpcData(await window.mango.stop())
      const next = unwrapIpcData(await window.mango.start(settings))
      setStatus(next)
      if (next.running) {
        startPendingRef.current = false
        setStartPending(false)
        setStartProgress('')
      }
      notify('Mango restarted.', 'success')
    } catch (err) {
      startPendingRef.current = false
      setStartPending(false)
      setStartProgress('')
      notify(`Failed to restart Mango: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [settings, notify])

  const saveSettings = useCallback(async () => {
    if (!window.mango) return
    try {
      const saved = unwrapIpcData(await window.mango.saveSettings(settings))
      setSettings(saved)
      setSavedSettings(saved)
      notify('Settings saved.', 'success')
    } catch (err) {
      notify(`Failed to save settings: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [settings, notify])

  const openLogsFolder = useCallback(async () => {
    if (!window.mango) return
    try {
      const res = unwrapIpcData(await window.mango.openLogsFolder())
      notify(`Opened logs folder: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to open logs folder: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [notify])

  const copyDiagnostics = useCallback(async () => {
    if (!window.mango) return
    try {
      unwrapIpcData(await window.mango.copyDiagnostics())
      notify('Diagnostics copied.', 'success')
    } catch (err) {
      notify(`Failed to copy diagnostics: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [notify])

  const exportUsageJson = useCallback(async (payload: object) => {
    if (!window.mango) return
    try {
      const res = unwrapIpcData(await window.mango.saveUsageReport('json', JSON.stringify(payload, null, 2)))
      notify(`Saved usage JSON: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to export JSON: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [notify])

  const exportUsageCsv = useCallback(async (csv: string) => {
    if (!window.mango) return
    try {
      const res = unwrapIpcData(await window.mango.saveUsageReport('csv', csv))
      notify(`Saved usage CSV: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to export CSV: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }, [notify])

  const settingsDirty = useMemo(
    () => JSON.stringify(settings) !== JSON.stringify(savedSettings),
    [settings, savedSettings],
  )

  return useMemo(
    () => ({
      status,
      settings,
      setSettings,
      savedSettings,
      settingsDirty,
      assistantState,
      setAssistantState,
      transcript,
      reply,
      globeVisible,
      setGlobeVisible,
      globeUrl,
      globeLabel,
      mapTarget,
      logs,
      conversationTimeline,
      setConversationTimeline,
      chatTimeline,
      setChatTimeline,
      turnMetrics,
      toolEvents,
      usageSamples,
      lastErrorAt,
      startPending,
      startProgress,
      chatSeqRef,
      pendingChatRequestRef,
      audioLevelRef,
      statusRunningRef,
      startMango,
      stopMango,
      restartMango,
      saveSettings,
      openLogsFolder,
      copyDiagnostics,
      exportUsageJson,
      exportUsageCsv,
    }),
    [
      status,
      settings,
      savedSettings,
      settingsDirty,
      assistantState,
      transcript,
      reply,
      globeVisible,
      globeUrl,
      globeLabel,
      mapTarget,
      logs,
      conversationTimeline,
      chatTimeline,
      turnMetrics,
      toolEvents,
      usageSamples,
      lastErrorAt,
      startPending,
      startProgress,
      startMango,
      stopMango,
      restartMango,
      saveSettings,
      openLogsFolder,
      copyDiagnostics,
      exportUsageJson,
      exportUsageCsv,
    ],
  )
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './styles/tokens.css'
import './App.css'
import { ToastStack } from './components/ToastStack'
import { TopBar } from './components/TopBar'
import { TabNav } from './components/TabNav'
import { MangoHud } from './components/MangoHud'
import { ChatPanel } from './components/ChatPanel'
import { ConversationPanel } from './components/ConversationPanel'
import { MetricsPanel } from './components/MetricsPanel'
import { SmartPanel } from './components/SmartPanel'
import { CommandPalette } from './components/CommandPalette'
import { SettingsPanel } from './components/SettingsPanel'
import type { SmartAction } from './lib/smartActions'
import { useToast } from './context/ToastContext'
import { useOrbCanvas } from './hooks/useOrbCanvas'
import { useMapView } from './hooks/useMapView'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useDiscordBridgeStatus } from './hooks/useDiscordBridgeStatus'
import { usePageVisible } from './hooks/usePageVisible'
import type { MangoEvent } from './types/events'
import type {
  AppView,
  LogEntry,
  MangoSettings,
  MangoStatus,
  MapTarget,
  OrbState,
  TimelineItem,
  ToolEvent,
  TurnMetrics,
  UsageSample,
} from './types/ui'

function App() {
  const { pushToast } = useToast()
  const [status, setStatus] = useState<MangoStatus>({ running: false, pid: null, startedAt: null })
  const [savedSettings, setSavedSettings] = useState<MangoSettings>({
    wakeEnabled: true,
    strictTools: false,
    powershellConfirmation: true,
    groqModel: 'llama-3.3-70b-versatile',
    edgeVoice: 'en-US-GuyNeural',
    edgeRate: '+0%',
    edgePitch: '+0Hz',
    edgeVolume: '+0%',
    interruptProfile: 'normal',
    promptTokenRatePer1k: 0,
    completionTokenRatePer1k: 0,
  })
  const [settings, setSettings] = useState<MangoSettings>(savedSettings)
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
  const [activeView, setActiveView] = useState<AppView>('mango')
  const [chatInput, setChatInput] = useState('')
  const [manualSending, setManualSending] = useState(false)
  const [chatAtBottom, setChatAtBottom] = useState(true)
  const [startPending, setStartPending] = useState(false)
  const [startProgress, setStartProgress] = useState('')
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  const orbWrapRef = useRef<HTMLDivElement | null>(null)
  const orbCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const chatFeedRef = useRef<HTMLDivElement | null>(null)
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null)
  const chatSeqRef = useRef(0)
  const pendingChatRequestRef = useRef<string | null>(null)
  const mapHostRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const mapTileLayerRef = useRef<L.TileLayer | null>(null)
  const mapTileErrorCountRef = useRef(0)
  const mapMarkerRef = useRef<L.CircleMarker | null>(null)
  const orbStateRef = useRef<OrbState>('idle')
  const audioLevelRef = useRef(0)
  const statusRunningRef = useRef(status.running)
  const speakingResetTimer = useRef<number | null>(null)
  const startPendingRef = useRef(false)
  const noiseHintAtRef = useRef(0)

  const pageVisible = usePageVisible()
  const discord = useDiscordBridgeStatus(true)

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

  const notify = useCallback(
    (message: string, kind: 'info' | 'success' | 'error' = 'info') => {
      if (!message) return
      pushToast(message, kind)
    },
    [pushToast],
  )

  useEffect(() => {
    if (!window.mango) {
      notify('Mango desktop bridge not detected. Open this UI from Electron.', 'error')
      return
    }
    let unsub: (() => void) | null = null
    void window.mango
      .getStatus()
      .then(setStatus)
      .catch((err) => notify(`Failed to load Mango status: ${String(err)}`, 'error'))
    void window.mango
      .getRecentLogs()
      .then((items) => setLogs(items.slice(-200)))
      .catch((err) => notify(`Failed to load logs: ${String(err)}`, 'error'))
    void window.mango
      .getSettings()
      .then((s) => {
        setSettings(s)
        setSavedSettings(s)
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
            // Keep speaking state through multi-step narration until level stays quiet.
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
            setMapTarget((prev) => ({
              lat,
              lng,
              zoom: zoom ?? prev.zoom,
            }))
          }
          setGlobeVisible(true)
          setActiveView('mango')
        }
        if (p.kind === 'globe_state') {
          setGlobeVisible(Boolean(p.visible))
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
      if (speakingResetTimer.current) {
        window.clearTimeout(speakingResetTimer.current)
      }
    }
  }, [armSpeakingReset, notify])

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

  const startedLabel = useMemo(() => {
    if (!status.startedAt) return 'Not started'
    return `Started ${new Date(status.startedAt).toLocaleTimeString()}`
  }, [status.startedAt])

  const orbState = useMemo((): OrbState => {
    if (lastErrorAt) return 'error'
    if (
      assistantState === 'idle' ||
      assistantState === 'listening' ||
      assistantState === 'thinking' ||
      assistantState === 'speaking' ||
      assistantState === 'awaiting' ||
      assistantState === 'stopped'
    ) {
      return assistantState
    }
    return status.running ? 'listening' : 'idle'
  }, [assistantState, status.running, lastErrorAt])

  orbStateRef.current = orbState

  const orbEnabled = activeView === 'mango' && pageVisible
  useOrbCanvas(orbEnabled, orbState, orbWrapRef, orbCanvasRef, audioLevelRef, orbStateRef)

  const onMapNotice = useCallback((msg: string) => notify(msg, 'info'), [notify])
  useMapView({
    active: activeView === 'mango',
    globeVisible,
    mapTarget,
    mapHostRef,
    mapRef,
    mapTileLayerRef,
    mapTileErrorCountRef,
    mapMarkerRef,
    onMapNotice,
  })

  useEffect(() => {
    if (activeView !== 'chat') return
    if (!chatAtBottom && !manualSending) return
    const host = chatFeedRef.current
    if (!host) return
    window.requestAnimationFrame(() => {
      host.scrollTop = host.scrollHeight
    })
  }, [activeView, chatTimeline.length, manualSending, chatAtBottom])

  const handleChatFeedScroll = useCallback((el: HTMLDivElement) => {
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    setChatAtBottom(distance < 80)
  }, [])

  const usageTotals = useMemo(() => {
    const totals = usageSamples.reduce(
      (acc, s) => {
        acc.prompt += s.promptTokens
        acc.completion += s.completionTokens
        acc.total += s.totalTokens
        return acc
      },
      { prompt: 0, completion: 0, total: 0 },
    )
    const estCost =
      (totals.prompt / 1000) * settings.promptTokenRatePer1k +
      (totals.completion / 1000) * settings.completionTokenRatePer1k
    return { ...totals, estCost }
  }, [usageSamples, settings.promptTokenRatePer1k, settings.completionTokenRatePer1k])

  const sortedChatTimeline = useMemo(
    () => [...chatTimeline].sort((a, b) => a.seq - b.seq),
    [chatTimeline],
  )

  const mapFallbackUrl =
    globeUrl ||
    `https://www.openstreetmap.org/#map/${Math.max(2, Math.min(19, Math.round(mapTarget.zoom)))}/${mapTarget.lat}/${mapTarget.lng}`

  async function startMango() {
    if (!window.mango) return
    try {
      startPendingRef.current = true
      setStartPending(true)
      setStartProgress('Starting Mango')
      const next = await window.mango.start(settings)
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
  }

  async function stopMango() {
    if (!window.mango) return
    try {
      const next = await window.mango.stop()
      setStatus(next)
      setAssistantState('stopped')
      startPendingRef.current = false
      setStartPending(false)
      setStartProgress('')
      notify('Mango stopped.', 'info')
    } catch (err) {
      notify(`Failed to stop Mango: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  async function restartMango() {
    if (!window.mango) return
    try {
      startPendingRef.current = true
      setStartPending(true)
      setStartProgress('Restarting Mango')
      notify('Restarting Mango…', 'info')
      await window.mango.stop()
      const next = await window.mango.start(settings)
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
  }

  async function saveSettings() {
    if (!window.mango) return
    try {
      const saved = await window.mango.saveSettings(settings)
      setSettings(saved)
      setSavedSettings(saved)
      notify('Settings saved.', 'success')
    } catch (err) {
      notify(`Failed to save settings: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  async function openLogsFolder() {
    if (!window.mango) return
    try {
      const res = await window.mango.openLogsFolder()
      if (res.ok) notify(`Opened logs folder: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to open logs folder: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  async function copyDiagnostics() {
    if (!window.mango) return
    try {
      const res = await window.mango.copyDiagnostics()
      if (res.ok) notify('Diagnostics copied.', 'success')
    } catch (err) {
      notify(`Failed to copy diagnostics: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  async function exportUsageJson() {
    if (!window.mango) return
    try {
      const payload = {
        exportedAt: new Date().toISOString(),
        status,
        settings,
        usageTotals,
        usageSamples,
        toolEvents,
        chatTimeline,
        conversationTimeline,
      }
      const res = await window.mango.saveUsageReport('json', JSON.stringify(payload, null, 2))
      if (res.ok) notify(`Saved usage JSON: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to export JSON: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  async function exportUsageCsv() {
    if (!window.mango) return
    try {
      const header = 'timestamp,prompt_tokens,completion_tokens,total_tokens,total_time_s,queue_time_s\n'
      const rows = usageSamples
        .map((u) =>
          [
            new Date(u.ts).toISOString(),
            u.promptTokens,
            u.completionTokens,
            u.totalTokens,
            u.totalTime ?? '',
            u.queueTime ?? '',
          ].join(','),
        )
        .join('\n')
      const res = await window.mango.saveUsageReport('csv', header + rows + '\n')
      if (res.ok) notify(`Saved usage CSV: ${res.path}`, 'success')
    } catch (err) {
      notify(`Failed to export CSV: ${err instanceof Error ? err.message : String(err)}`, 'error')
    }
  }

  const sendManualMessage = useCallback(async (textOverride?: string) => {
    const text = (textOverride ?? chatInput).trim()
    if (!text || manualSending) return
    if (!window.mango) {
      notify('Mango desktop bridge not detected. Open this UI from Electron.', 'error')
      return
    }
    const now = Date.now()
    const priorHistory = chatTimeline
      .filter((item) => !item.pending)
      .slice(-20)
      .map((item) => ({ role: item.role, text: item.text }))
    const submitHistory = [...priorHistory, { role: 'user' as const, text }]
    const requestId = `chat-${now}`
    pendingChatRequestRef.current = requestId
    chatSeqRef.current += 1
    const userSeq = chatSeqRef.current
    if (!textOverride) setChatInput('')
    setChatTimeline((prev) => [
      ...prev.slice(-49),
      { id: `${requestId}-user`, seq: userSeq, ts: now, role: 'user', text },
    ])
    chatSeqRef.current += 1
    const pendingSeq = chatSeqRef.current
    setChatTimeline((prev) => [
      ...prev.slice(-49),
      {
        id: `${requestId}-pending`,
        seq: pendingSeq,
        ts: now,
        role: 'assistant',
        text: 'Thinking…',
        pending: true,
      },
    ])
    setManualSending(true)
    setAssistantState('thinking')
    try {
      const res = await window.mango.sendText(text, submitHistory)
      if (pendingChatRequestRef.current !== requestId) return
      if (!res.ok) {
        throw new Error(res.error || 'No response from manual text bridge.')
      }
      const replyText = String(res.reply || '').trim() || 'Done.'
      setChatTimeline((prev) => {
        const withoutPending = prev.filter((item) => item.id !== `${requestId}-pending`)
        return [
          ...withoutPending.slice(-49),
          {
            id: `${requestId}-assistant`,
            seq: pendingSeq,
            ts: Date.now(),
            role: 'assistant',
            text: replyText,
          },
        ]
      })
      setAssistantState(statusRunningRef.current ? 'listening' : 'idle')
    } catch (err) {
      if (pendingChatRequestRef.current === requestId) {
        setChatTimeline((prev) => {
          const withoutPending = prev.filter((item) => item.id !== `${requestId}-pending`)
          return [
            ...withoutPending.slice(-49),
            {
              id: `${requestId}-error`,
              seq: pendingSeq,
              ts: Date.now(),
              role: 'assistant',
              text: `Error: ${err instanceof Error ? err.message : String(err)}`,
            },
          ]
        })
        notify(`Manual message failed: ${err instanceof Error ? err.message : String(err)}`, 'error')
      }
      setAssistantState(statusRunningRef.current ? 'listening' : 'idle')
    } finally {
      if (pendingChatRequestRef.current === requestId) {
        pendingChatRequestRef.current = null
      }
      setManualSending(false)
    }
  }, [chatInput, chatTimeline, manualSending, notify])

  const sendSmartPrompt = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return
      setActiveView('chat')
      void sendManualMessage(trimmed)
    },
    [sendManualMessage],
  )

  const handleSmartAction = useCallback(
    (action: SmartAction) => {
      if (action.id === 'open_smart' || action.id === 'remember') {
        setActiveView('smart')
        if (action.id === 'remember') notify('Add a memory card on the Smart tab.', 'info')
        return
      }
      if (action.prompt) sendSmartPrompt(action.prompt)
    },
    [sendSmartPrompt, notify],
  )

  const setPromptDraft = useCallback(
    (text: string) => {
      setChatInput(text)
      if (activeView !== 'chat') {
        setActiveView('chat')
      }
      window.requestAnimationFrame(() => {
        chatInputRef.current?.focus()
        const len = text.length
        chatInputRef.current?.setSelectionRange(len, len)
      })
    },
    [activeView],
  )

  function clearConversation() {
    setChatTimeline([])
    pendingChatRequestRef.current = null
    notify('Chat cleared.', 'info')
  }

  useKeyboardShortcuts(
    setActiveView,
    () => void sendManualMessage(),
    activeView,
    () => setCommandPaletteOpen((open) => !open),
    () => {
      setGlobeVisible(false)
      setActiveView('mango')
    },
    () => void saveSettings(),
  )

  return (
    <div className={`app state-${orbState}${commandPaletteOpen ? ' modalOpen' : ''}`}>
      <TopBar
        status={status}
        orbState={orbState}
        startedLabel={startedLabel}
        discord={discord}
        startPending={startPending}
        onStart={() => void startMango()}
        onStop={() => void stopMango()}
        onRestart={() => void restartMango()}
      />

      {status.running && !discord.reachable ? (
        <p className="bridgeBanner" role="status">
          Discord voice bridge is offline — run{' '}
          <code>scripts/start-mango-discord.ps1</code> for call music and ducking.
        </p>
      ) : null}

      <ToastStack />

      <main className="workspace">
        <div className={`viewPane ${activeView === 'mango' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'mango'}>
          <MangoHud
            orbState={orbState}
            running={status.running}
            transcript={transcript}
            reply={reply}
            globeVisible={globeVisible}
            globeLabel={globeLabel}
            hasGlobeUrl={Boolean(globeUrl)}
            orbWrapRef={orbWrapRef}
            orbCanvasRef={orbCanvasRef}
            mapHostRef={mapHostRef}
            onBackFromMap={() => setGlobeVisible(false)}
            onOpenExternal={() => window.open(mapFallbackUrl, '_blank', 'noopener,noreferrer')}
            onResumeMap={() => {
              setGlobeVisible(true)
              setActiveView('mango')
            }}
            onStart={() => void startMango()}
            startPending={startPending}
            startProgress={startProgress}
            turnMetrics={turnMetrics}
            latestToolEvent={toolEvents[toolEvents.length - 1] ?? null}
            onQuickPrompt={setPromptDraft}
          />
        </div>

        <div className={`viewPane ${activeView === 'chat' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'chat'}>
          <ChatPanel
            timeline={sortedChatTimeline}
            chatInput={chatInput}
            manualSending={manualSending}
            chatFeedRef={chatFeedRef}
            chatInputRef={chatInputRef}
            onInput={setChatInput}
            onSend={() => void sendManualMessage()}
            onClear={clearConversation}
            onPrompt={setPromptDraft}
            onFeedScroll={handleChatFeedScroll}
          />
        </div>

        <div
          className={`viewPane viewPaneScroll ${activeView === 'conversation' ? 'viewActive' : ''}`}
          aria-hidden={activeView !== 'conversation'}
        >
          <ConversationPanel
            transcript={transcript}
            reply={reply}
            timeline={conversationTimeline}
            logs={logs}
          />
        </div>

        <div className={`viewPane viewPaneScroll ${activeView === 'metrics' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'metrics'}>
          <MetricsPanel
            turnMetrics={turnMetrics}
            toolEvents={toolEvents}
            usageSamples={usageSamples}
            usageTotals={usageTotals}
          />
        </div>

        <div className={`viewPane viewPaneScroll ${activeView === 'smart' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'smart'}>
          <SmartPanel onNotify={notify} onSendPrompt={sendSmartPrompt} />
        </div>

        <div
          className={`viewPane viewPaneScroll ${activeView === 'settings' ? 'viewActive' : ''}`}
          aria-hidden={activeView !== 'settings'}
        >
          <SettingsPanel
            settings={settings}
            savedSettings={savedSettings}
            onChange={setSettings}
            onSave={() => void saveSettings()}
            onOpenLogs={() => void openLogsFolder()}
            onCopyDiagnostics={() => void copyDiagnostics()}
            onExportJson={() => void exportUsageJson()}
            onExportCsv={() => void exportUsageCsv()}
          />
        </div>
      </main>

      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onRunAction={handleSmartAction}
      />

      <TabNav
        activeView={activeView}
        onView={setActiveView}
        onMangoTab={() => {
          setGlobeVisible(false)
          setActiveView('mango')
        }}
      />
    </div>
  )
}

export default App

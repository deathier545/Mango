import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './styles/tokens.css'
import './styles/studio.css'
import './App.css'
import { ToastStack } from './components/ToastStack'
import { TopBar } from './components/TopBar'
import { SmartPanel } from './components/SmartPanel'
import { CommandPalette } from './components/CommandPalette'
import { SettingsDrawer } from './components/shell/SettingsDrawer'
import { NavRail } from './components/shell/NavRail'
import { OrbDock } from './components/shell/OrbDock'
import { TelemetryStrip } from './components/shell/TelemetryStrip'
import { CommandBar } from './components/shell/CommandBar'
import { CommandView } from './components/shell/CommandView'
import { DiagnosticsView } from './components/shell/DiagnosticsView'
import { ContextRail, type ContextRailMode } from './components/shell/ContextRail'
import { OrbMobileFab } from './components/shell/OrbMobileFab'
import type { SmartAction } from './lib/smartActions'
import { runPaletteCommand, type PaletteCommand, type PaletteContext } from './lib/commandRegistry'
import { useToast } from './context/ToastContext'
import { useOrbCanvas } from './hooks/useOrbCanvas'
import { useMapView } from './hooks/useMapView'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useDiscordBridgeStatus } from './hooks/useDiscordBridgeStatus'
import { usePageVisible } from './hooks/usePageVisible'
import { useUnifiedFeed, type FeedFilter, type FeedToolItem } from './hooks/useUnifiedFeed'
import { useMangoBridge } from './hooks/useMangoBridge'
import { useBadgeUnlockWatcher } from './hooks/useBadgeUnlockWatcher'
import type { AppZone, DiagSubView, OrbState, ToolEvent } from './types/ui'

function App() {
  const { pushToast } = useToast()
  const [activeZone, setActiveZone] = useState<AppZone>('command')
  const [diagSubView, setDiagSubView] = useState<DiagSubView>('metrics')
  const [feedFilter, setFeedFilter] = useState<FeedFilter>('all')
  const [contextRailOpen, setContextRailOpen] = useState(false)
  const [contextRailMode, setContextRailMode] = useState<ContextRailMode>('idle')
  const [contextTool, setContextTool] = useState<ToolEvent | null>(null)
  const [contextRailWidth, setContextRailWidth] = useState(320)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const zoneBeforeSettingsRef = useRef<AppZone>('command')
  const [orbDockCollapsed, setOrbDockCollapsed] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [manualSending, setManualSending] = useState(false)
  const [chatAtBottom, setChatAtBottom] = useState(true)
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  const orbWrapRef = useRef<HTMLDivElement | null>(null)
  const orbCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const chatFeedRef = useRef<HTMLDivElement | null>(null)
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null)
  const mapHostRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const mapTileLayerRef = useRef<L.TileLayer | null>(null)
  const mapTileErrorCountRef = useRef(0)
  const mapMarkerRef = useRef<L.CircleMarker | null>(null)
  const orbStateRef = useRef<OrbState>('idle')

  const pageVisible = usePageVisible()
  const discord = useDiscordBridgeStatus(true)

  const notify = useCallback(
    (message: string, kind: 'info' | 'success' | 'error' = 'info') => {
      if (!message) return
      pushToast(message, kind)
    },
    [pushToast],
  )

  const onGlobeOpen = useCallback(() => {
    setContextRailMode('map')
    setContextRailOpen(true)
  }, [])

  const onGlobeVisibleChange = useCallback((visible: boolean) => {
    if (visible) {
      setContextRailMode('map')
      setContextRailOpen(true)
    }
  }, [])

  const globeHandlers = useMemo(
    () => ({ onGlobeOpen, onGlobeVisibleChange }),
    [onGlobeOpen, onGlobeVisibleChange],
  )

  const {
    status,
    settings,
    setSettings,
    savedSettings,
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
    saveAndRestartMango,
    openLogsFolder,
    copyDiagnostics,
    exportUsageJson: bridgeExportJson,
    exportUsageCsv: bridgeExportCsv,
  } = useMangoBridge(notify, globeHandlers)

  useBadgeUnlockWatcher(status.running, notify)

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

  const orbEnabled = pageVisible
  useOrbCanvas(orbEnabled, orbState, orbWrapRef, orbCanvasRef, audioLevelRef, orbStateRef)

  const onMapNotice = useCallback((msg: string) => notify(msg, 'info'), [notify])
  useMapView({
    active: contextRailOpen && globeVisible,
    globeVisible,
    mapTarget,
    mapHostRef,
    mapRef,
    mapTileLayerRef,
    mapTileErrorCountRef,
    mapMarkerRef,
    onMapNotice,
  })

  const unifiedFeed = useUnifiedFeed(
    conversationTimeline,
    chatTimeline,
    toolEvents,
    turnMetrics,
    feedFilter,
  )

  useEffect(() => {
    if (activeZone !== 'command') return
    if (!chatAtBottom && !manualSending) return
    const host = chatFeedRef.current
    if (!host) return
    window.requestAnimationFrame(() => {
      host.scrollTop = host.scrollHeight
    })
  }, [activeZone, chatTimeline.length, manualSending, chatAtBottom, unifiedFeed.length])

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

  const mapFallbackUrl =
    globeUrl ||
    `https://www.openstreetmap.org/#map/${Math.max(2, Math.min(19, Math.round(mapTarget.zoom)))}/${mapTarget.lat}/${mapTarget.lng}`

  async function exportUsageJson() {
    await bridgeExportJson({
      exportedAt: new Date().toISOString(),
      status,
      settings,
      usageTotals,
      usageSamples,
      toolEvents,
      chatTimeline,
      conversationTimeline,
    })
  }

  async function exportUsageCsv() {
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
    await bridgeExportCsv(header + rows + '\n')
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
      setActiveZone('command')
      void sendManualMessage(trimmed)
    },
    [sendManualMessage],
  )

  const handleSmartAction = useCallback(
    (action: SmartAction) => {
      if (action.id === 'open_smart' || action.id === 'remember') {
        setActiveZone('intelligence')
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
      setActiveZone('command')
      window.requestAnimationFrame(() => {
        chatInputRef.current?.focus()
        const len = text.length
        chatInputRef.current?.setSelectionRange(len, len)
      })
    },
    [],
  )

  const openSettings = useCallback(() => {
    zoneBeforeSettingsRef.current = activeZone === 'config' ? zoneBeforeSettingsRef.current : activeZone
    setActiveZone('config')
    setSettingsOpen(true)
  }, [activeZone])

  const closeSettings = useCallback(() => {
    setSettingsOpen(false)
    if (activeZone === 'config') {
      setActiveZone(zoneBeforeSettingsRef.current)
    }
  }, [activeZone])

  const openToolContext = useCallback((tool: ToolEvent) => {
    setContextTool(tool)
    setContextRailMode('tool')
    setContextRailOpen(true)
  }, [])

  const openToolFromFeed = useCallback(
    (item: FeedToolItem) => {
      openToolContext({
        ts: item.ts,
        correlationId: item.correlationId,
        tool: item.tool,
        risk: item.risk,
        event: item.event,
        ok: item.ok,
        durationMs: item.durationMs ?? null,
      })
    },
    [openToolContext],
  )

  const paletteContext = useMemo(
    (): PaletteContext => ({
      setZone: (zone) => {
        if (zone === 'config') openSettings()
        else setActiveZone(zone)
      },
      openSettings,
      startMango: () => void startMango(),
      stopMango: () => void stopMango(),
      restartMango: () => void restartMango(),
      clearTyped: clearTypedConversation,
      clearAll: clearAllConversation,
      openLogs: () => void openLogsFolder(),
      copyDiagnostics: () => void copyDiagnostics(),
      toggleContextRail: () => setContextRailOpen((o) => !o),
      running: status.running,
    }),
    [openSettings, status.running],
  )

  const handlePaletteCommand = useCallback(
    (command: PaletteCommand) => {
      if (command.smartAction) {
        handleSmartAction(command.smartAction)
        return
      }
      runPaletteCommand(command.id, paletteContext, handleSmartAction)
    },
    [paletteContext, handleSmartAction],
  )

  const handleZoneChange = useCallback(
    (zone: AppZone) => {
      if (zone === 'config') {
        openSettings()
        return
      }
      setActiveZone(zone)
    },
    [openSettings],
  )

  function clearTypedConversation() {
    setChatTimeline([])
    pendingChatRequestRef.current = null
    notify('Typed messages cleared.', 'info')
  }

  function clearAllConversation() {
    setChatTimeline([])
    setConversationTimeline([])
    pendingChatRequestRef.current = null
    notify('Conversation cleared.', 'info')
  }

  useKeyboardShortcuts(
    handleZoneChange,
    () => void sendManualMessage(),
    activeZone,
    () => setCommandPaletteOpen((open) => !open),
    () => setContextRailOpen((open) => !open),
    openSettings,
    chatInputRef,
  )

  const studioBodyStyle = contextRailOpen
    ? ({ ['--context-rail-w' as string]: `${contextRailWidth}px` } as CSSProperties)
    : undefined

  const studioBodyClass = [
    'studio-body',
    orbDockCollapsed ? 'orb-collapsed' : '',
    contextRailOpen ? 'context-open' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={`studio-app app state-${orbState}${commandPaletteOpen ? ' modalOpen' : ''}`}>
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

      <TelemetryStrip
        turnMetrics={turnMetrics}
        latestTool={toolEvents[toolEvents.length - 1] ?? null}
        tokenTotal={usageTotals.total}
        running={status.running}
        assistantState={assistantState}
        onToolClick={openToolContext}
      />

      <ToastStack />

      <div className="studio-middle">
        {status.running && !discord.reachable ? (
          <p className="bridgeBanner" role="status">
            Discord voice bridge is offline — run{' '}
            <code>scripts/start-mango-discord.ps1</code> for call music and ducking.
          </p>
        ) : null}

        <div className={studioBodyClass} style={studioBodyStyle}>
        <NavRail activeZone={activeZone} onZone={handleZoneChange} />

        <OrbDock
          orbState={orbState}
          running={status.running}
          collapsed={orbDockCollapsed}
          transcript={transcript}
          reply={reply}
          orbWrapRef={orbWrapRef}
          orbCanvasRef={orbCanvasRef}
          onToggleCollapse={() => setOrbDockCollapsed((v) => !v)}
          onStart={() => void startMango()}
          startPending={startPending}
          startProgress={startProgress}
        />

        <main className="studio-main">
          {activeZone === 'command' ? (
            <CommandView
              items={unifiedFeed}
              feedRef={chatFeedRef}
              filter={feedFilter}
              onFilter={setFeedFilter}
              onClearTyped={clearTypedConversation}
              onClearAll={clearAllConversation}
              onScroll={handleChatFeedScroll}
              onToolClick={openToolFromFeed}
              running={status.running}
              onStart={() => void startMango()}
              startPending={startPending}
            />
          ) : null}

          {activeZone === 'intelligence' ? (
            <SmartPanel onNotify={notify} onSendPrompt={sendSmartPrompt} />
          ) : null}

          {activeZone === 'diagnostics' ? (
            <DiagnosticsView
              subView={diagSubView}
              onSubView={setDiagSubView}
              transcript={transcript}
              reply={reply}
              voiceTimeline={conversationTimeline}
              logs={logs}
              turnMetrics={turnMetrics}
              toolEvents={toolEvents}
              usageSamples={usageSamples}
              usageTotals={usageTotals}
            />
          ) : null}

          {activeZone === 'config' ? (
            <div className="zoneView configPlaceholder glass-panel">
              <h2>Settings</h2>
              <p className="panelSub">Adjust preferences in the panel on the right, or press Esc to close.</p>
              <button type="button" className="glassBtnPrimary" onClick={openSettings}>
                Open settings
              </button>
            </div>
          ) : null}
        </main>

        <ContextRail
          open={contextRailOpen}
          mode={contextRailMode}
          width={contextRailWidth}
          onResize={setContextRailWidth}
          globeVisible={globeVisible}
          globeLabel={globeLabel}
          hasGlobeUrl={Boolean(globeUrl)}
          tool={contextTool}
          mapHostRef={mapHostRef}
          onClose={() => setContextRailOpen(false)}
          onBackFromMap={() => {
            setGlobeVisible(false)
            setContextRailMode(contextTool ? 'tool' : 'idle')
          }}
          onOpenExternal={() => window.open(mapFallbackUrl, '_blank', 'noopener,noreferrer')}
        />
        </div>
      </div>

      <CommandBar
        value={chatInput}
        sending={manualSending}
        inputRef={chatInputRef}
        onChange={setChatInput}
        onSend={() => void sendManualMessage()}
        onPrompt={setPromptDraft}
        assistantState={assistantState}
      />

      <OrbMobileFab
        orbState={orbState}
        running={status.running}
        onPress={() => {
          setActiveZone('command')
          window.requestAnimationFrame(() => chatInputRef.current?.focus())
        }}
      />

      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        paletteContext={paletteContext}
        onRunCommand={handlePaletteCommand}
      />

      <SettingsDrawer
        open={settingsOpen}
        running={status.running}
        settings={settings}
        savedSettings={savedSettings}
        onChange={setSettings}
        onClose={closeSettings}
        onSave={() => void saveSettings()}
        onSaveAndRestart={() => void saveAndRestartMango()}
        onOpenLogs={() => void openLogsFolder()}
        onCopyDiagnostics={() => void copyDiagnostics()}
        onExportJson={() => void exportUsageJson()}
        onExportCsv={() => void exportUsageCsv()}
      />
    </div>
  )
}

export default App

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
import { DiagnosticsPanel } from './components/DiagnosticsPanel'
import { SmartPanel } from './components/SmartPanel'
import { CommandPalette } from './components/CommandPalette'
import { SettingsPanel } from './components/SettingsPanel'
import { ConfirmDialog } from './components/ConfirmDialog'
import type { SmartAction } from './lib/smartActions'
import { useToast } from './context/ToastContext'
import { useOrbCanvas } from './hooks/useOrbCanvas'
import { useMapView } from './hooks/useMapView'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useDiscordBridgeStatus } from './hooks/useDiscordBridgeStatus'
import { usePageVisible } from './hooks/usePageVisible'
import { useDuoChat } from './hooks/useDuoChat'
import { useMangoBridge } from './hooks/useMangoBridge'
import type { AppView, DiagSubView, OrbState } from './types/ui'

function App() {
  const { pushToast } = useToast()
  const [activeView, setActiveView] = useState<AppView>('mango')
  const [diagSubView, setDiagSubView] = useState<DiagSubView>('metrics')
  const [settingsOpen, setSettingsOpen] = useState(false)
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

  const onGlobeOpen = useCallback(() => setActiveView('mango'), [])

  const globeHandlers = useMemo(() => ({ onGlobeOpen }), [onGlobeOpen])

  const mango = useMangoBridge(notify, globeHandlers)
  const duo = useDuoChat(notify)

  const {
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
    statusRunningRef,
    audioLevelRef,
    startMango,
    stopMango,
    restartMango,
    saveSettings,
    openLogsFolder,
    copyDiagnostics,
    exportUsageJson: saveUsageJson,
    exportUsageCsv: saveUsageCsv,
  } = mango

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

  const orbEnabled = activeView === 'mango' && pageVisible && !duo.duoMode
  useOrbCanvas(orbEnabled, orbState, orbWrapRef, orbCanvasRef, audioLevelRef, orbStateRef)

  const onMapNotice = useCallback((msg: string) => notify(msg, 'info'), [notify])
  useMapView({
    active: activeView === 'mango' && globeVisible,
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

  async function exportUsageJson() {
    await saveUsageJson({
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
    await saveUsageCsv(header + rows + '\n')
  }

  const sendManualMessage = useCallback(
    async (textOverride?: string) => {
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
    },
    [chatInput, chatTimeline, manualSending, setChatTimeline, setAssistantState, notify],
  )

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
      if (activeView !== 'chat') setActiveView('chat')
      window.requestAnimationFrame(() => {
        chatInputRef.current?.focus()
        const len = text.length
        chatInputRef.current?.setSelectionRange(len, len)
      })
    },
    [activeView],
  )

  const clearConversation = useCallback(() => {
    setChatTimeline([])
    pendingChatRequestRef.current = null
    notify('Chat cleared.', 'info')
  }, [setChatTimeline, notify])

  const [confirmDiscardSettings, setConfirmDiscardSettings] = useState(false)

  const openSettings = useCallback(() => setSettingsOpen(true), [])

  const closeSettings = useCallback(() => {
    setSettingsOpen(false)
    setConfirmDiscardSettings(false)
  }, [])

  const requestCloseSettings = useCallback(() => {
    if (settingsDirty) {
      setConfirmDiscardSettings(true)
      return
    }
    closeSettings()
  }, [settingsDirty, closeSettings])

  const discardSettings = useCallback(() => {
    setSettings(savedSettings)
  }, [savedSettings, setSettings])

  useEffect(() => {
    if (!settingsOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !confirmDiscardSettings) {
        e.preventDefault()
        requestCloseSettings()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [settingsOpen, requestCloseSettings, confirmDiscardSettings])

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
    settingsDirty,
    openSettings,
  )

  return (
    <div className={`app state-${orbState}${commandPaletteOpen || settingsOpen ? ' modalOpen' : ''}`}>
      <TopBar
        status={status}
        orbState={orbState}
        startedLabel={startedLabel}
        discord={discord}
        startPending={startPending}
        onStart={() => void startMango()}
        onStop={() => void stopMango()}
        onRestart={() => void restartMango()}
        onOpenSettings={openSettings}
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
            duoMode={duo.duoMode}
            onEnterDuo={duo.enterDuoMode}
            duoEnabled={activeView === 'mango' && pageVisible}
            mangoDuoState={duo.mangoDuoState}
            amberDuoState={duo.amberDuoState}
            duoTopic={duo.duoTopic}
            duoRounds={duo.duoRounds}
            duoRunning={duo.duoRunning}
            duoLines={duo.duoLines}
            onDuoTopicChange={duo.setDuoTopic}
            onDuoRoundsChange={duo.setDuoRounds}
            onStartDuo={() => void duo.startDuo()}
            onExitDuo={duo.exitDuoMode}
            mangoDuoAudioRef={duo.mangoAudioRef}
            amberDuoAudioRef={duo.amberAudioRef}
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
          className={`viewPane viewPaneScroll ${activeView === 'diagnostics' ? 'viewActive' : ''}`}
          aria-hidden={activeView !== 'diagnostics'}
        >
          <DiagnosticsPanel
            subView={diagSubView}
            onSubView={setDiagSubView}
            transcript={transcript}
            reply={reply}
            timeline={conversationTimeline}
            logs={logs}
            turnMetrics={turnMetrics}
            toolEvents={toolEvents}
            usageSamples={usageSamples}
            usageTotals={usageTotals}
          />
        </div>

        <div className={`viewPane viewPaneScroll ${activeView === 'smart' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'smart'}>
          <SmartPanel onNotify={notify} onSendPrompt={sendSmartPrompt} />
        </div>
      </main>

      {settingsOpen ? (
        <div
          className="settingsOverlay"
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
          onClick={requestCloseSettings}
        >
          <div className="settingsOverlayInner panel" onClick={(e) => e.stopPropagation()}>
            <header className="settingsOverlayHead">
              <div>
                <h2>Settings</h2>
                {settingsDirty ? <span className="unsavedBadge">Unsaved changes</span> : null}
              </div>
              <button type="button" className="ghostBtn" onClick={requestCloseSettings} aria-label="Close settings">
                ✕
              </button>
            </header>
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
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmDiscardSettings}
        title="Discard changes?"
        message="You have unsaved settings. Discard changes and close?"
        confirmLabel="Discard"
        cancelLabel="Keep editing"
        onConfirm={() => {
          setConfirmDiscardSettings(false)
          discardSettings()
          closeSettings()
        }}
        onCancel={() => setConfirmDiscardSettings(false)}
      />

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

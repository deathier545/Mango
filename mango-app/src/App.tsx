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
import type { SmartAction } from './lib/smartActions'
import { useToast } from './context/ToastContext'
import { useOrbCanvas } from './hooks/useOrbCanvas'
import { useMapView } from './hooks/useMapView'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useDiscordBridgeStatus } from './hooks/useDiscordBridgeStatus'
import { usePageVisible } from './hooks/usePageVisible'
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

  const startedLabel = useMemo(() => {
    if (!mango.status.startedAt) return 'Not started'
    return `Started ${new Date(mango.status.startedAt).toLocaleTimeString()}`
  }, [mango.status.startedAt])

  const orbState = useMemo((): OrbState => {
    if (mango.lastErrorAt) return 'error'
    if (
      mango.assistantState === 'idle' ||
      mango.assistantState === 'listening' ||
      mango.assistantState === 'thinking' ||
      mango.assistantState === 'speaking' ||
      mango.assistantState === 'awaiting' ||
      mango.assistantState === 'stopped'
    ) {
      return mango.assistantState
    }
    return mango.status.running ? 'listening' : 'idle'
  }, [mango.assistantState, mango.status.running, mango.lastErrorAt])

  orbStateRef.current = orbState

  const orbEnabled = activeView === 'mango' && pageVisible
  useOrbCanvas(orbEnabled, orbState, orbWrapRef, orbCanvasRef, mango.audioLevelRef, orbStateRef)

  const onMapNotice = useCallback((msg: string) => notify(msg, 'info'), [notify])
  useMapView({
    active: activeView === 'mango' && mango.globeVisible,
    globeVisible: mango.globeVisible,
    mapTarget: mango.mapTarget,
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
  }, [activeView, mango.chatTimeline.length, manualSending, chatAtBottom])

  const handleChatFeedScroll = useCallback((el: HTMLDivElement) => {
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    setChatAtBottom(distance < 80)
  }, [])

  const usageTotals = useMemo(() => {
    const totals = mango.usageSamples.reduce(
      (acc, s) => {
        acc.prompt += s.promptTokens
        acc.completion += s.completionTokens
        acc.total += s.totalTokens
        return acc
      },
      { prompt: 0, completion: 0, total: 0 },
    )
    const estCost =
      (totals.prompt / 1000) * mango.settings.promptTokenRatePer1k +
      (totals.completion / 1000) * mango.settings.completionTokenRatePer1k
    return { ...totals, estCost }
  }, [mango.usageSamples, mango.settings.promptTokenRatePer1k, mango.settings.completionTokenRatePer1k])

  const sortedChatTimeline = useMemo(
    () => [...mango.chatTimeline].sort((a, b) => a.seq - b.seq),
    [mango.chatTimeline],
  )

  const mapFallbackUrl =
    mango.globeUrl ||
    `https://www.openstreetmap.org/#map/${Math.max(2, Math.min(19, Math.round(mango.mapTarget.zoom)))}/${mango.mapTarget.lat}/${mango.mapTarget.lng}`

  async function exportUsageJson() {
    await mango.exportUsageJson({
      exportedAt: new Date().toISOString(),
      status: mango.status,
      settings: mango.settings,
      usageTotals,
      usageSamples: mango.usageSamples,
      toolEvents: mango.toolEvents,
      chatTimeline: mango.chatTimeline,
      conversationTimeline: mango.conversationTimeline,
    })
  }

  async function exportUsageCsv() {
    const header = 'timestamp,prompt_tokens,completion_tokens,total_tokens,total_time_s,queue_time_s\n'
    const rows = mango.usageSamples
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
    await mango.exportUsageCsv(header + rows + '\n')
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
      const priorHistory = mango.chatTimeline
        .filter((item) => !item.pending)
        .slice(-20)
        .map((item) => ({ role: item.role, text: item.text }))
      const submitHistory = [...priorHistory, { role: 'user' as const, text }]
      const requestId = `chat-${now}`
      mango.pendingChatRequestRef.current = requestId
      mango.chatSeqRef.current += 1
      const userSeq = mango.chatSeqRef.current
      if (!textOverride) setChatInput('')
      mango.setChatTimeline((prev) => [
        ...prev.slice(-49),
        { id: `${requestId}-user`, seq: userSeq, ts: now, role: 'user', text },
      ])
      mango.chatSeqRef.current += 1
      const pendingSeq = mango.chatSeqRef.current
      mango.setChatTimeline((prev) => [
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
      mango.setAssistantState('thinking')
      try {
        const res = await window.mango.sendText(text, submitHistory)
        if (mango.pendingChatRequestRef.current !== requestId) return
        if (!res.ok) {
          throw new Error(res.error || 'No response from manual text bridge.')
        }
        const replyText = String(res.reply || '').trim() || 'Done.'
        mango.setChatTimeline((prev) => {
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
        mango.setAssistantState(mango.statusRunningRef.current ? 'listening' : 'idle')
      } catch (err) {
        if (mango.pendingChatRequestRef.current === requestId) {
          mango.setChatTimeline((prev) => {
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
        mango.setAssistantState(mango.statusRunningRef.current ? 'listening' : 'idle')
      } finally {
        if (mango.pendingChatRequestRef.current === requestId) {
          mango.pendingChatRequestRef.current = null
        }
        setManualSending(false)
      }
    },
    [chatInput, manualSending, mango, notify],
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
    mango.setChatTimeline([])
    mango.pendingChatRequestRef.current = null
    notify('Chat cleared.', 'info')
  }, [mango, notify])

  const openSettings = useCallback(() => setSettingsOpen(true), [])
  const closeSettings = useCallback(() => setSettingsOpen(false), [])

  useEffect(() => {
    if (!settingsOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        closeSettings()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [settingsOpen, closeSettings])

  useKeyboardShortcuts(
    setActiveView,
    () => void sendManualMessage(),
    activeView,
    () => setCommandPaletteOpen((open) => !open),
    () => {
      mango.setGlobeVisible(false)
      setActiveView('mango')
    },
    () => void mango.saveSettings(),
    settingsOpen,
    openSettings,
  )

  return (
    <div className={`app state-${orbState}${commandPaletteOpen || settingsOpen ? ' modalOpen' : ''}`}>
      <TopBar
        status={mango.status}
        orbState={orbState}
        startedLabel={startedLabel}
        discord={discord}
        startPending={mango.startPending}
        onStart={() => void mango.startMango()}
        onStop={() => void mango.stopMango()}
        onRestart={() => void mango.restartMango()}
        onOpenSettings={openSettings}
      />

      {mango.status.running && !discord.reachable ? (
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
            running={mango.status.running}
            transcript={mango.transcript}
            reply={mango.reply}
            globeVisible={mango.globeVisible}
            globeLabel={mango.globeLabel}
            hasGlobeUrl={Boolean(mango.globeUrl)}
            orbWrapRef={orbWrapRef}
            orbCanvasRef={orbCanvasRef}
            mapHostRef={mapHostRef}
            onBackFromMap={() => mango.setGlobeVisible(false)}
            onOpenExternal={() => window.open(mapFallbackUrl, '_blank', 'noopener,noreferrer')}
            onResumeMap={() => {
              mango.setGlobeVisible(true)
              setActiveView('mango')
            }}
            onStart={() => void mango.startMango()}
            startPending={mango.startPending}
            startProgress={mango.startProgress}
            turnMetrics={mango.turnMetrics}
            latestToolEvent={mango.toolEvents[mango.toolEvents.length - 1] ?? null}
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
          className={`viewPane viewPaneScroll ${activeView === 'diagnostics' ? 'viewActive' : ''}`}
          aria-hidden={activeView !== 'diagnostics'}
        >
          <DiagnosticsPanel
            subView={diagSubView}
            onSubView={setDiagSubView}
            transcript={mango.transcript}
            reply={mango.reply}
            timeline={mango.conversationTimeline}
            logs={mango.logs}
            turnMetrics={mango.turnMetrics}
            toolEvents={mango.toolEvents}
            usageSamples={mango.usageSamples}
            usageTotals={usageTotals}
          />
        </div>

        <div className={`viewPane viewPaneScroll ${activeView === 'smart' ? 'viewActive' : ''}`} aria-hidden={activeView !== 'smart'}>
          <SmartPanel onNotify={notify} onSendPrompt={sendSmartPrompt} />
        </div>

        {settingsOpen ? (
          <div className="settingsOverlay viewPane viewActive viewPaneScroll" role="dialog" aria-modal="true" aria-label="Settings">
            <div className="settingsOverlayInner panel">
              <header className="settingsOverlayHead">
                <h2>Settings</h2>
                <button type="button" className="ghostBtn" onClick={closeSettings} aria-label="Close settings">
                  ✕
                </button>
              </header>
              <SettingsPanel
                settings={mango.settings}
                savedSettings={mango.savedSettings}
                onChange={mango.setSettings}
                onSave={() => void mango.saveSettings()}
                onOpenLogs={() => void mango.openLogsFolder()}
                onCopyDiagnostics={() => void mango.copyDiagnostics()}
                onExportJson={() => void exportUsageJson()}
                onExportCsv={() => void exportUsageCsv()}
              />
            </div>
          </div>
        ) : null}
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
          mango.setGlobeVisible(false)
          setActiveView('mango')
        }}
      />
    </div>
  )
}

export default App

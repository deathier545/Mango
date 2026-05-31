type MangoStatus = {
  running: boolean
  pid: number | null
  startedAt: number | null
}

type MangoSettings = {
  wakeEnabled: boolean
  strictTools: boolean
  powershellConfirmation: boolean
  safeMode: boolean
  groqModel: string
  edgeVoice: string
  edgeRate: string
  edgePitch: string
  edgeVolume: string
  interruptProfile: 'strict' | 'normal' | 'fast'
  promptTokenRatePer1k: number
  completionTokenRatePer1k: number
}

type MangoEventPayload =
  | { type: 'log'; payload: { ts: number; kind: string; line: string } }
  | { type: 'status'; payload: MangoStatus }
  | {
      type: 'parsed'
      payload:
        | { kind: 'state'; state: string; text: string }
        | { kind: 'audio_level'; level: number }
        | {
            kind: 'globe'
            url: string
            label: string
            lat: number | null
            lng: number | null
            zoom?: number | null
          }
        | { kind: 'globe_state'; visible: boolean }
        | { kind: 'transcript'; text: string }
        | { kind: 'reply'; text: string }
        | {
            kind: 'metric_turn'
            event: string
            correlationId: string | null
            source: string
            sttS: number | null
            llmS: number | null
            ttsS: number | null
          }
        | {
            kind: 'metric_tool'
            event: string
            correlationId: string | null
            tool: string
            risk: string
            ok: boolean | null
            durationMs?: number | null
          }
        | {
            kind: 'metric_usage'
            promptTokens: number
            completionTokens: number
            totalTokens: number
            totalTime: number | null
            queueTime: number | null
          }
        | { kind: 'duo_phase'; speaker: string; phase: string; text: string }
    }

type ChatHistoryItem = {
  role: 'user' | 'assistant'
  text: string
}

type IpcResult<T> = { ok: true; data: T } | { ok: false; error: string }

interface Window {
  mango: {
    getStatus: () => Promise<MangoStatus | IpcResult<MangoStatus>>
    getDiscordBridgeStatus: () => Promise<
      | {
          reachable: boolean
          ok: boolean
          musicOn: boolean
          ownerVoice: string | null
        }
      | IpcResult<{
          reachable: boolean
          ok: boolean
          musicOn: boolean
          ownerVoice: string | null
        }>
    >
    getRecentLogs: () => Promise<
      Array<{ ts: number; kind: string; line: string }> | IpcResult<Array<{ ts: number; kind: string; line: string }>>
    >
    getSettings: () => Promise<MangoSettings | IpcResult<MangoSettings>>
    saveSettings: (settings: MangoSettings) => Promise<MangoSettings | IpcResult<MangoSettings>>
    start: (settings?: Partial<MangoSettings>) => Promise<MangoStatus | IpcResult<MangoStatus>>
    stop: () => Promise<MangoStatus | IpcResult<MangoStatus>>
    sendText: (
      text: string,
      history?: ChatHistoryItem[],
    ) => Promise<{ ok: boolean; reply?: string; error?: string }>
    runDuo: (payload: {
      topic: string
      rounds?: number
      speak?: boolean
    }) => Promise<
      | {
          ok: boolean
          lines?: Array<{ speaker: string; text: string }>
          topic?: string
          rounds?: number
          error?: string
        }
      | IpcResult<{
          ok: boolean
          lines?: Array<{ speaker: string; text: string }>
          topic?: string
          rounds?: number
          error?: string
        }>
    >
    openLogsFolder: () => Promise<{ path: string } | IpcResult<{ path: string }>>
    copyDiagnostics: () => Promise<{ text: string } | IpcResult<{ text: string }>>
    saveUsageReport: (kind: 'json' | 'csv', content: string) => Promise<{ path: string } | IpcResult<{ path: string }>>
    smartSnapshot: () => Promise<{ ok: boolean; data?: unknown; error?: string }>
    smartBrief: () => Promise<{ ok: boolean; text?: string; error?: string }>
    smartCardAdd: (payload: {
      title?: string
      content?: string
      category?: string
    }) => Promise<{ ok: boolean; card?: unknown; error?: string }>
    smartCardDelete: (cardId: string) => Promise<{ ok: boolean; error?: string }>
    smartInboxAdd: (text: string) => Promise<{ ok: boolean; item?: unknown; error?: string }>
    onEvent: (cb: (payload: MangoEventPayload) => void) => () => void
  }
}

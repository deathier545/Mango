export type MangoStatus = {
  running: boolean
  pid: number | null
  startedAt: number | null
}

export type MangoSettings = {
  wakeEnabled: boolean
  strictTools: boolean
  powershellConfirmation: boolean
  groqModel: string
  edgeVoice: string
  edgeRate: string
  edgePitch: string
  edgeVolume: string
  interruptProfile: 'strict' | 'normal' | 'fast'
  promptTokenRatePer1k: number
  completionTokenRatePer1k: number
}

export type AppZone = 'command' | 'intelligence' | 'diagnostics' | 'config'

/** @deprecated use AppZone */
export type AppView = AppZone

export type DiagSubView = 'metrics' | 'voice' | 'system'

export type MemoryCard = {
  id: string
  title: string
  content: string
  category: 'person' | 'preference' | 'device' | 'fact' | 'task'
  created_at?: string
  updated_at?: string
}

export type SmartRoutine = {
  id: string
  name: string
  description: string
  steps?: unknown[]
}

export type TimelineEntry = {
  ts: number
  tool: string
  risk: string
  ok: boolean
  duration_ms?: number | null
  result_preview?: string
  correlation_id?: string | null
  error_code?: string | null
}

export type BadgeCategory =
  | 'memory'
  | 'skills'
  | 'routines'
  | 'tools'
  | 'integrations'
  | 'continuity'
  | 'smart'
  | 'discord'
  | 'voice'

export type MangoBadge = {
  id: string
  title: string
  description: string
  category: BadgeCategory
  icon: string
  unlocked: boolean
  hint?: string
  progress?: { current: number; target: number }
}

export type BadgeSnapshot = {
  badges: MangoBadge[]
  summary: { unlocked: number; total: number; percent: number }
}

export type SmartSnapshot = {
  cards: MemoryCard[]
  routines: SmartRoutine[]
  inbox: Array<{ id: string; text: string; tags?: string[]; created_at?: string }>
  timeline: TimelineEntry[]
  badges?: BadgeSnapshot
}

export type OrbState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'awaiting'
  | 'stopped'
  | 'error'

export type TimelineItem = {
  id: string
  seq: number
  ts: number
  role: 'user' | 'assistant'
  text: string
  pending?: boolean
}

export type TurnMetrics = {
  correlationId: string | null
  source: string
  sttS: number | null
  llmS: number | null
  ttsS: number | null
}

export type ToolEvent = {
  ts: number
  correlationId: string | null
  tool: string
  risk: string
  event: string
  ok: boolean | null
  durationMs?: number | null
}

export type UsageSample = {
  ts: number
  promptTokens: number
  completionTokens: number
  totalTokens: number
  totalTime: number | null
  queueTime: number | null
}

export type MapTarget = {
  lat: number
  lng: number
  zoom: number
}

export type LogEntry = {
  ts: number
  kind: string
  line: string
}

export type DiscordBridgeStatus = {
  ok: boolean
  musicOn: boolean
  ownerVoice: string | null
  reachable: boolean
}

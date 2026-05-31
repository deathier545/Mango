export type ParsedEvent =
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
  | {
      kind: 'noise_guidance'
      source: string
      noiseFloor: number | null
      recommendation: string
    }
  | {
      kind: 'duo_phase'
      speaker: string
      phase: string
      text: string
    }
  | {
      kind: 'duo_done'
      ok: boolean
      lines: Array<{ speaker?: string; text?: string }>
      error: string
    }

export type MangoEvent =
  | { type: 'log'; payload: { ts: number; kind: string; line: string } }
  | { type: 'status'; payload: { running: boolean; pid: number | null; startedAt: number | null } }
  | { type: 'parsed'; payload: ParsedEvent }

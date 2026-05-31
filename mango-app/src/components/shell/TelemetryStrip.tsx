import type { TurnMetrics, ToolEvent } from '../../types/ui'
import { formatLatency } from '../../lib/format'

type TelemetryStripProps = {
  turnMetrics: TurnMetrics | null
  latestTool: ToolEvent | null
  tokenTotal: number
  running: boolean
  assistantState: string
  onToolClick?: (tool: ToolEvent) => void
}

export function TelemetryStrip({
  turnMetrics,
  latestTool,
  tokenTotal,
  running,
  assistantState,
  onToolClick,
}: TelemetryStripProps) {
  const pills: {
    key: string
    label: string
    tone: 'live' | 'ok' | 'warn' | 'muted'
    clickable?: boolean
    onClick?: () => void
  }[] = []

  if (running) {
    const tone =
      assistantState === 'error' ? 'warn' : assistantState === 'thinking' ? 'warn' : 'live'
    pills.push({ key: 'state', label: assistantState.toUpperCase(), tone })
  } else {
    pills.push({ key: 'state', label: 'OFFLINE', tone: 'muted' })
  }

  if (turnMetrics?.sttS != null) {
    pills.push({ key: 'stt', label: `STT ${formatLatency(turnMetrics.sttS)}`, tone: 'ok' })
  }
  if (turnMetrics?.llmS != null) {
    pills.push({ key: 'llm', label: `LLM ${formatLatency(turnMetrics.llmS)}`, tone: 'ok' })
  }
  if (turnMetrics?.ttsS != null) {
    pills.push({ key: 'tts', label: `TTS ${formatLatency(turnMetrics.ttsS)}`, tone: 'ok' })
  }
  if (latestTool) {
    const ok = latestTool.ok === true ? 'ok' : latestTool.ok === false ? 'warn' : 'muted'
    pills.push({
      key: 'tool',
      label: `${latestTool.tool} ${latestTool.ok === true ? '✓' : latestTool.ok === false ? '✗' : '…'}`,
      tone: ok,
      clickable: true,
      onClick: () => onToolClick?.(latestTool),
    })
  }
  if (tokenTotal > 0) {
    pills.push({ key: 'tok', label: `${tokenTotal.toLocaleString()} tok`, tone: 'muted' })
  }

  return (
    <div className="telemetryStrip" role="status" aria-live="polite">
      <span className="telemetryLabel">LIVE</span>
      <div className="telemetryPills">
        {pills.map((p) =>
          p.clickable ? (
            <button
              key={p.key}
              type="button"
              className={`telemetryPill telemetryPill-${p.tone} telemetryPill-btn`}
              onClick={p.onClick}
              title="Open tool details"
            >
              {p.label}
            </button>
          ) : (
            <span key={p.key} className={`telemetryPill telemetryPill-${p.tone}`}>
              {p.label}
            </span>
          ),
        )}
      </div>
    </div>
  )
}

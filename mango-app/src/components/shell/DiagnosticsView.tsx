import type { DiagSubView, LogEntry, TimelineItem, ToolEvent, TurnMetrics, UsageSample } from '../../types/ui'
import { ConversationPanel } from '../ConversationPanel'
import { MetricsPanel } from '../MetricsPanel'

type DiagnosticsViewProps = {
  subView: DiagSubView
  onSubView: (view: DiagSubView) => void
  transcript: string
  reply: string
  voiceTimeline: TimelineItem[]
  logs: LogEntry[]
  turnMetrics: TurnMetrics | null
  toolEvents: ToolEvent[]
  usageSamples: UsageSample[]
  usageTotals: {
    prompt: number
    completion: number
    total: number
    estCost: number
  }
}

const SUB_TABS: { id: DiagSubView; label: string }[] = [
  { id: 'metrics', label: 'Metrics' },
  { id: 'voice', label: 'Voice log' },
  { id: 'system', label: 'System log' },
]

export function DiagnosticsView({
  subView,
  onSubView,
  transcript,
  reply,
  voiceTimeline,
  logs,
  turnMetrics,
  toolEvents,
  usageSamples,
  usageTotals,
}: DiagnosticsViewProps) {
  return (
    <div className="zoneView diagnosticsView">
      <nav className="diagSubNav" aria-label="Diagnostics sections">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={subView === tab.id ? 'diagSubTab active' : 'diagSubTab'}
            aria-current={subView === tab.id ? 'page' : undefined}
            onClick={() => onSubView(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {subView === 'metrics' ? (
        <MetricsPanel
          turnMetrics={turnMetrics}
          toolEvents={toolEvents}
          usageSamples={usageSamples}
          usageTotals={usageTotals}
        />
      ) : null}

      {subView === 'voice' ? (
        <ConversationPanel
          transcript={transcript}
          reply={reply}
          timeline={voiceTimeline}
          logs={logs}
          voiceOnly
        />
      ) : null}

      {subView === 'system' ? (
        <ConversationPanel
          transcript={transcript}
          reply={reply}
          timeline={voiceTimeline}
          logs={logs}
          logsOnly
        />
      ) : null}
    </div>
  )
}

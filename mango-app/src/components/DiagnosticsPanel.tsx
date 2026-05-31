import type { DiagSubView, LogEntry, TimelineItem, ToolEvent, TurnMetrics, UsageSample } from '../types/ui'
import { ConversationPanel } from './ConversationPanel'
import { MetricsPanel } from './MetricsPanel'

type UsageTotals = {
  prompt: number
  completion: number
  total: number
  estCost: number
}

type DiagnosticsPanelProps = {
  subView: DiagSubView
  onSubView: (view: DiagSubView) => void
  transcript: string
  reply: string
  timeline: TimelineItem[]
  logs: LogEntry[]
  turnMetrics: TurnMetrics | null
  toolEvents: ToolEvent[]
  usageSamples: UsageSample[]
  usageTotals: UsageTotals
}

const SUB_TABS: { id: DiagSubView; label: string }[] = [
  { id: 'voice', label: 'Voice' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'system', label: 'System' },
]

export function DiagnosticsPanel({
  subView,
  onSubView,
  transcript,
  reply,
  timeline,
  logs,
  turnMetrics,
  toolEvents,
  usageSamples,
  usageTotals,
}: DiagnosticsPanelProps) {
  return (
    <div className="diagnosticsPanel">
      <nav className="diagSubTabs" aria-label="Diagnostics sections">
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

      {subView === 'voice' ? (
        <ConversationPanel
          transcript={transcript}
          reply={reply}
          timeline={timeline}
          logs={logs}
          section="voice"
        />
      ) : null}

      {subView === 'system' ? (
        <ConversationPanel
          transcript={transcript}
          reply={reply}
          timeline={timeline}
          logs={logs}
          section="system"
        />
      ) : null}

      {subView === 'metrics' ? (
        <MetricsPanel
          turnMetrics={turnMetrics}
          toolEvents={toolEvents}
          usageSamples={usageSamples}
          usageTotals={usageTotals}
        />
      ) : null}
    </div>
  )
}

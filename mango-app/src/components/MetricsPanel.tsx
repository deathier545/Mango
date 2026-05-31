import { useMemo } from 'react'
import type { ToolEvent, TurnMetrics, UsageSample } from '../types/ui'
import { useAnimatedNumber } from '../hooks/useAnimatedNumber'
import { ToolTimelineRow } from './ToolTimelineRow'

type MetricsPanelProps = {
  turnMetrics: TurnMetrics | null
  toolEvents: ToolEvent[]
  usageSamples: UsageSample[]
  usageTotals: { prompt: number; completion: number; total: number; estCost: number }
}

function MetricValue({ value, suffix = '' }: { value: number | null | undefined; suffix?: string }) {
  const animated = useAnimatedNumber(value ?? null, (n) => `${n.toFixed(2)}${suffix}`)
  return <strong>{value != null ? animated : '—'}</strong>
}

function TokenValue({ value }: { value: number | undefined }) {
  const animated = useAnimatedNumber(value ?? null, (n) => Math.round(n).toLocaleString())
  return <strong>{value != null ? animated : '—'}</strong>
}

export function MetricsPanel({ turnMetrics, toolEvents, usageSamples, usageTotals }: MetricsPanelProps) {
  const latestUsage = usageSamples.length ? usageSamples[usageSamples.length - 1] : null
  const reversedTools = useMemo(() => [...toolEvents].reverse(), [toolEvents])

  return (
    <section className="contentGrid">
      <section className="panel">
        <h2>Latency</h2>
        <section className="metricsStrip">
          <div className="metricCard">
            <span className="metricLabel">STT</span>
            <MetricValue value={turnMetrics?.sttS} suffix="s" />
          </div>
          <div className="metricCard">
            <span className="metricLabel">LLM</span>
            <MetricValue value={turnMetrics?.llmS} suffix="s" />
          </div>
          <div className="metricCard">
            <span className="metricLabel">TTS</span>
            <MetricValue value={turnMetrics?.ttsS} suffix="s" />
          </div>
        </section>
        <p className="metricMeta">
          Source: {turnMetrics?.source || '—'} · Turn ID: {turnMetrics?.correlationId || '—'}
        </p>

        <h2>Usage & cost</h2>
        <section className="usageStrip">
          <div className="metricCard">
            <span className="metricLabel">Prompt tokens</span>
            <TokenValue value={latestUsage?.promptTokens} />
          </div>
          <div className="metricCard">
            <span className="metricLabel">Completion tokens</span>
            <TokenValue value={latestUsage?.completionTokens} />
          </div>
          <div className="metricCard">
            <span className="metricLabel">Total tokens</span>
            <TokenValue value={latestUsage?.totalTokens} />
          </div>
        </section>
        <p className="metricMeta">
          Session total: {usageTotals.total.toLocaleString()} · Estimated cost: ${usageTotals.estCost.toFixed(4)}
        </p>
      </section>

      <section className="panel">
        <h2>Tool calls</h2>
        <p className="metricMeta">Tap a row for event details. Newest first.</p>
        <div className="tools toolTimelineList">
          {reversedTools.length === 0 ? (
            <p className="empty">No tool events yet.</p>
          ) : (
            reversedTools.map((item, idx) => {
              const failed = item.ok === false
              const eventLabel = item.event.replace('tool_', '')
              const details = [
                { label: 'Risk:', value: item.risk || '—' },
                { label: 'Event:', value: eventLabel },
                ...(item.correlationId
                  ? [{ label: 'Correlation:', value: item.correlationId }]
                  : []),
              ]
              return (
                <ToolTimelineRow
                  key={`${item.ts}-${idx}`}
                  timeLabel={new Date(item.ts).toLocaleTimeString()}
                  tool={item.tool}
                  risk={item.risk}
                  statusLabel={item.ok === null ? '—' : item.ok ? 'ok' : 'fail'}
                  durationLabel={item.durationMs != null ? `${item.durationMs}ms` : '—'}
                  failed={failed}
                  details={details}
                />
              )
            })
          )}
        </div>
      </section>
    </section>
  )
}

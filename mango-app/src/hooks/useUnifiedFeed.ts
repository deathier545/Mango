import { useMemo } from 'react'
import type { TimelineItem, ToolEvent, TurnMetrics } from '../types/ui'

export type FeedFilter = 'all' | 'messages' | 'voice' | 'typed' | 'tools'

export type FeedMessageItem = TimelineItem & {
  kind: 'message'
  channel: 'voice' | 'typed'
}

export type FeedToolItem = {
  kind: 'tool'
  id: string
  ts: number
  tool: string
  risk: string
  event: string
  ok: boolean | null
  durationMs?: number | null
  correlationId: string | null
}

export type FeedTurnGroup = {
  kind: 'turn'
  id: string
  ts: number
  correlationId: string | null
  items: Array<FeedMessageItem | FeedToolItem>
  metrics?: Pick<TurnMetrics, 'sttS' | 'llmS' | 'ttsS'> | null
}

export type FeedDisplayItem = FeedMessageItem | FeedToolItem | FeedTurnGroup

export type UnifiedFeedItem = FeedMessageItem

function toMessages(voice: TimelineItem[], chat: TimelineItem[]): FeedMessageItem[] {
  return [
    ...voice.map((item) => ({ ...item, kind: 'message' as const, channel: 'voice' as const })),
    ...chat.map((item) => ({ ...item, kind: 'message' as const, channel: 'typed' as const })),
  ]
}

function toTools(events: ToolEvent[]): FeedToolItem[] {
  return events.map((e, i) => ({
    kind: 'tool' as const,
    id: `tool-${e.ts}-${i}`,
    ts: e.ts,
    tool: e.tool,
    risk: e.risk,
    event: e.event,
    ok: e.ok,
    durationMs: e.durationMs,
    correlationId: e.correlationId,
  }))
}

function groupIntoTurns(
  rows: Array<FeedMessageItem | FeedToolItem>,
  turnMetrics: TurnMetrics | null,
): FeedDisplayItem[] {
  const out: FeedDisplayItem[] = []
  const used = new Set<string>()

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]
    if (used.has(row.id)) continue

    const corr = row.kind === 'tool' ? row.correlationId : null
    const canGroup =
      corr &&
      rows.some((r, j) => j !== i && !used.has(r.id) && r.kind === 'tool' && r.correlationId === corr)

    if (!canGroup && !(corr && rows.filter((r) => r.kind === 'tool' && r.correlationId === corr).length > 0)) {
      const related = corr
        ? rows.filter((r) => {
            if (used.has(r.id)) return false
            if (r.kind === 'tool' && r.correlationId === corr) return true
            if (r.kind === 'message' && Math.abs(r.ts - row.ts) < 120_000) return true
            return false
          })
        : [row]

      if (related.length > 1 && corr) {
        related.forEach((r) => used.add(r.id))
        const metrics =
          turnMetrics?.correlationId === corr
            ? { sttS: turnMetrics.sttS, llmS: turnMetrics.llmS, ttsS: turnMetrics.ttsS }
            : null
        out.push({
          kind: 'turn',
          id: `turn-${corr}-${row.ts}`,
          ts: Math.min(...related.map((r) => r.ts)),
          correlationId: corr,
          items: related.sort((a, b) => a.ts - b.ts),
          metrics,
        })
        continue
      }
    }

    if (used.has(row.id)) continue
    used.add(row.id)
    out.push(row)
  }

  return out.sort((a, b) => a.ts - b.ts)
}

export function useUnifiedFeed(
  voiceTimeline: TimelineItem[],
  chatTimeline: TimelineItem[],
  toolEvents: ToolEvent[],
  turnMetrics: TurnMetrics | null,
  filter: FeedFilter = 'all',
  groupTurns = true,
): FeedDisplayItem[] {
  return useMemo(() => {
    const messages = toMessages(voiceTimeline, chatTimeline)
    const tools = toTools(toolEvents)

    if (filter === 'tools') {
      return tools.sort((a, b) => a.ts - b.ts)
    }

    let msgFiltered = messages
    if (filter === 'voice') msgFiltered = messages.filter((m) => m.channel === 'voice')
    if (filter === 'typed') msgFiltered = messages.filter((m) => m.channel === 'typed')

    if (filter === 'messages' || filter === 'voice' || filter === 'typed') {
      return msgFiltered.sort((a, b) => a.ts - b.ts || a.seq - b.seq)
    }

    const merged = [...msgFiltered, ...tools].sort((a, b) => a.ts - b.ts)
    if (!groupTurns || merged.length === 0) return merged

    return groupIntoTurns(merged, turnMetrics)
  }, [voiceTimeline, chatTimeline, toolEvents, turnMetrics, filter, groupTurns])
}

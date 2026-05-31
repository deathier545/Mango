import { useCallback, useEffect, useMemo, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { RefObject } from 'react'
import type { FeedDisplayItem, FeedFilter, FeedMessageItem, FeedToolItem, FeedTurnGroup } from '../../hooks/useUnifiedFeed'
import { cleanUiText, formatLatency } from '../../lib/format'
import { CopyButton } from '../CopyButton'

type UnifiedFeedProps = {
  items: FeedDisplayItem[]
  feedRef: RefObject<HTMLDivElement | null>
  filter: FeedFilter
  onFilter: (filter: FeedFilter) => void
  onClearTyped: () => void
  onClearAll: () => void
  onScroll: (el: HTMLDivElement) => void
  onToolClick?: (item: FeedToolItem) => void
  running: boolean
  onStart: () => void
  startPending: boolean
}

const FILTERS: { id: FeedFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'messages', label: 'Messages' },
  { id: 'voice', label: 'Voice' },
  { id: 'typed', label: 'Typed' },
  { id: 'tools', label: 'Tools' },
]

const CHANNEL_LABEL: Record<'voice' | 'typed', string> = {
  voice: 'Voice',
  typed: 'Typed',
}

const VIRTUAL_THRESHOLD = 40

function estimateRowHeight(item: FeedDisplayItem): number {
  if (item.kind === 'turn') return 160 + item.items.length * 72
  if (item.kind === 'tool') return 56
  const lines = Math.ceil(item.text.length / 60)
  return 72 + Math.min(lines, 6) * 18
}

function MessageBubble({ item }: { item: FeedMessageItem }) {
  return (
    <article
      className={`feedBubble ${item.role}${item.pending ? ' pending' : ''}`}
      aria-busy={item.pending ? true : undefined}
    >
      <div className="feedBubbleHead">
        <span className={`feedBadge feedBadge-${item.channel}`}>{CHANNEL_LABEL[item.channel]}</span>
        <span className="chatMeta">{item.role === 'user' ? 'You' : 'Mango'}</span>
        <time className="chatMeta" dateTime={new Date(item.ts).toISOString()}>
          {new Date(item.ts).toLocaleTimeString()}
        </time>
        {!item.pending ? <CopyButton text={item.text} /> : null}
      </div>
      <p className="feedText">{cleanUiText(item.text)}</p>
    </article>
  )
}

function ToolBubble({ item, onClick }: { item: FeedToolItem; onClick?: () => void }) {
  const ok = item.ok === true ? 'ok' : item.ok === false ? 'fail' : 'pending'
  const inner = (
    <>
      <span className="feedToolIcon" aria-hidden="true">
        ⚙
      </span>
      <div className="feedToolBody">
        <span className="feedToolName">{item.tool}</span>
        <span className="feedToolMeta">
          {item.event}
          {item.durationMs != null ? ` · ${item.durationMs}ms` : ''}
        </span>
      </div>
      <span className={`feedToolStatus feedToolStatus-${ok}`}>
        {item.ok === true ? 'OK' : item.ok === false ? 'Fail' : '…'}
      </span>
      <time className="chatMeta" dateTime={new Date(item.ts).toISOString()}>
        {new Date(item.ts).toLocaleTimeString()}
      </time>
    </>
  )

  if (onClick) {
    return (
      <button type="button" className={`feedToolRow feedTool-${ok} feedToolRow-btn`} onClick={onClick}>
        {inner}
      </button>
    )
  }

  return <article className={`feedToolRow feedTool-${ok}`}>{inner}</article>
}

function TurnGroupCard({
  group,
  onToolClick,
}: {
  group: FeedTurnGroup
  onToolClick?: (item: FeedToolItem) => void
}) {
  const { metrics } = group
  return (
    <article className="feedTurnGroup glass-panel">
      <header className="feedTurnHead">
        <span className="feedTurnLabel">Turn</span>
        <time className="chatMeta" dateTime={new Date(group.ts).toISOString()}>
          {new Date(group.ts).toLocaleTimeString()}
        </time>
      </header>
      <div className="feedTurnItems">
        {group.items.map((item) =>
          item.kind === 'message' ? (
            <MessageBubble key={item.id} item={item} />
          ) : (
            <ToolBubble key={item.id} item={item} onClick={onToolClick ? () => onToolClick(item) : undefined} />
          ),
        )}
      </div>
      {metrics && (metrics.sttS != null || metrics.llmS != null || metrics.ttsS != null) ? (
        <footer className="feedTurnMetrics">
          {metrics.sttS != null ? <span>STT {formatLatency(metrics.sttS)}</span> : null}
          {metrics.llmS != null ? <span>LLM {formatLatency(metrics.llmS)}</span> : null}
          {metrics.ttsS != null ? <span>TTS {formatLatency(metrics.ttsS)}</span> : null}
        </footer>
      ) : null}
    </article>
  )
}

function FeedRow({
  item,
  onToolClick,
}: {
  item: FeedDisplayItem
  onToolClick?: (item: FeedToolItem) => void
}) {
  if (item.kind === 'turn') return <TurnGroupCard group={item} onToolClick={onToolClick} />
  if (item.kind === 'tool') {
    return <ToolBubble item={item} onClick={onToolClick ? () => onToolClick(item) : undefined} />
  }
  return <MessageBubble item={item} />
}

export function UnifiedFeed({
  items,
  feedRef,
  filter,
  onFilter,
  onClearTyped,
  onClearAll,
  onScroll,
  onToolClick,
  running,
  onStart,
  startPending,
}: UnifiedFeedProps) {
  const [showScrollDown, setShowScrollDown] = useState(false)
  const displayItems = useMemo(() => items, [items])
  const useVirtual = displayItems.length >= VIRTUAL_THRESHOLD

  const virtualizer = useVirtualizer({
    count: displayItems.length,
    getScrollElement: () => feedRef.current,
    estimateSize: (index) => estimateRowHeight(displayItems[index]),
    overscan: 10,
  })

  const handleScroll = useCallback(
    (el: HTMLDivElement) => {
      onScroll(el)
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight
      setShowScrollDown(distance > 120)
    },
    [onScroll],
  )

  useEffect(() => {
    const el = feedRef.current
    if (el) handleScroll(el)
  }, [displayItems.length, feedRef, handleScroll, virtualizer.range?.endIndex])

  const scrollToBottom = () => {
    const el = feedRef.current
    if (!el) return
    if (useVirtual) {
      virtualizer.scrollToIndex(displayItems.length - 1, { align: 'end' })
    } else {
      el.scrollTop = el.scrollHeight
    }
    handleScroll(el)
  }

  return (
    <section className="unifiedFeed glass-panel">
      <header className="unifiedFeedHead">
        <div>
          <h2>Conversation</h2>
          <p className="panelSub">
            Voice, typed chat, and tools in one place
            {displayItems.length > 0 ? ` · ${displayItems.length} items` : ''}.
          </p>
        </div>
        <div className="unifiedFeedActions">
          <button type="button" className="ghostBtn" onClick={onClearTyped}>
            Clear typed
          </button>
          <button type="button" className="ghostBtn" onClick={onClearAll}>
            Clear all
          </button>
        </div>
      </header>

      <div className="feedFilters" role="tablist" aria-label="Filter conversation">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            className={filter === f.id ? 'feedFilter active' : 'feedFilter'}
            onClick={() => onFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="unifiedFeedBody">
        <div
          className="unifiedFeedScroll"
          ref={feedRef}
          role="log"
          aria-live="polite"
          onScroll={(e) => handleScroll(e.currentTarget)}
        >
          {displayItems.length === 0 ? (
            <div className="feedEmpty">
              <p className="feedEmptyTitle">Start talking to Mango</p>
              <p className="feedEmptySub">
                Say &ldquo;hey mango&rdquo; or hold Alt+W, or type in the command bar below.
              </p>
              {!running ? (
                <button type="button" className="glassBtnPrimary" disabled={startPending} onClick={onStart}>
                  {startPending ? 'Starting…' : 'Start Mango'}
                </button>
              ) : null}
            </div>
          ) : useVirtual ? (
            <div className="feedVirtualInner" style={{ height: virtualizer.getTotalSize() }}>
              {virtualizer.getVirtualItems().map((vRow) => (
                <div
                  key={vRow.key}
                  className="feedVirtualRow"
                  data-index={vRow.index}
                  ref={virtualizer.measureElement}
                  style={{ transform: `translateY(${vRow.start}px)` }}
                >
                  <FeedRow item={displayItems[vRow.index]} onToolClick={onToolClick} />
                </div>
              ))}
            </div>
          ) : (
            displayItems.map((item) => <FeedRow key={item.id} item={item} onToolClick={onToolClick} />)
          )}
        </div>

        {showScrollDown ? (
          <button type="button" className="feedScrollDown" onClick={scrollToBottom}>
            Jump to latest
          </button>
        ) : null}
      </div>
    </section>
  )
}

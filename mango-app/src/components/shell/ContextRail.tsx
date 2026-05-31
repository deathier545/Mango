import { useCallback, useEffect, useRef, type PointerEvent, type RefObject } from 'react'
import type { ToolEvent } from '../../types/ui'
import { formatLatency } from '../../lib/format'

export type ContextRailMode = 'idle' | 'map' | 'tool'

type ContextRailProps = {
  open: boolean
  mode: ContextRailMode
  width: number
  onResize: (width: number) => void
  globeVisible: boolean
  globeLabel: string
  hasGlobeUrl: boolean
  tool: ToolEvent | null
  mapHostRef: RefObject<HTMLDivElement | null>
  onClose: () => void
  onBackFromMap: () => void
  onOpenExternal: () => void
}

const MIN_W = 280
const MAX_W = 520

export function ContextRail({
  open,
  mode,
  width,
  onResize,
  globeVisible,
  globeLabel,
  hasGlobeUrl,
  tool,
  mapHostRef,
  onClose,
  onBackFromMap,
  onOpenExternal,
}: ContextRailProps) {
  const dragRef = useRef<{ startX: number; startW: number } | null>(null)

  const onPointerDown = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      dragRef.current = { startX: e.clientX, startW: width }
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    },
    [width],
  )

  const onPointerMove = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      if (!dragRef.current) return
      const delta = dragRef.current.startX - e.clientX
      const next = Math.max(MIN_W, Math.min(MAX_W, dragRef.current.startW + delta))
      onResize(next)
    },
    [onResize],
  )

  const onPointerUp = useCallback(() => {
    dragRef.current = null
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const title = mode === 'map' ? globeLabel : mode === 'tool' && tool ? tool.tool : 'Context'

  return (
    <aside className="contextRail glass-panel" style={{ width }} aria-label="Context panel">
      <div
        className="contextRailResize"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panel"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      />

      <header className="contextRailHead">
        <h3>{title}</h3>
        <button type="button" className="ghostBtn" onClick={onClose} aria-label="Close context panel">
          ✕
        </button>
      </header>

      {mode === 'map' && globeVisible ? (
        <div className="contextMapWrap">
          <div className="mapHost" ref={mapHostRef} />
          <div className="contextMapActions">
            <button type="button" className="ghostBtn" onClick={onBackFromMap}>
              Close map
            </button>
            {hasGlobeUrl ? (
              <button type="button" className="ghostBtn" onClick={onOpenExternal}>
                Open in browser
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {mode === 'tool' && tool ? (
        <div className="contextToolDetail">
          <dl className="contextToolMeta">
            <div>
              <dt>Tool</dt>
              <dd>{tool.tool}</dd>
            </div>
            <div>
              <dt>Event</dt>
              <dd>{tool.event}</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>{tool.risk}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{tool.ok === true ? 'OK' : tool.ok === false ? 'Failed' : 'Pending'}</dd>
            </div>
            {tool.durationMs != null ? (
              <div>
                <dt>Duration</dt>
                <dd>{formatLatency(tool.durationMs / 1000)}</dd>
              </div>
            ) : null}
            {tool.correlationId ? (
              <div>
                <dt>Turn</dt>
                <dd className="contextToolMono">{tool.correlationId.slice(0, 8)}</dd>
              </div>
            ) : null}
            <div>
              <dt>Time</dt>
              <dd>{new Date(tool.ts).toLocaleTimeString()}</dd>
            </div>
          </dl>
        </div>
      ) : null}

      {mode === 'idle' ? (
        <p className="contextEmpty">Map and tool details appear here when Mango uses location or runs tools.</p>
      ) : null}
    </aside>
  )
}

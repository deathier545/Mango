import type { RefObject } from 'react'
import type { OrbState } from '../../types/ui'
import { assistantStateLabel } from '../../lib/format'

type OrbDockProps = {
  orbState: OrbState
  running: boolean
  collapsed: boolean
  transcript: string
  reply: string
  orbWrapRef: RefObject<HTMLDivElement | null>
  orbCanvasRef: RefObject<HTMLCanvasElement | null>
  onToggleCollapse: () => void
  onStart: () => void
  startPending: boolean
  startProgress: string
}

const RING_COLORS: Record<OrbState, string> = {
  idle: 'var(--ui-text-faint)',
  listening: 'var(--ui-cyan)',
  thinking: 'var(--ui-warning)',
  speaking: 'var(--ui-success)',
  awaiting: 'var(--ui-mango)',
  stopped: 'var(--ui-text-faint)',
  error: 'var(--ui-danger)',
}

export function OrbDock({
  orbState,
  running,
  collapsed,
  transcript,
  reply,
  orbWrapRef,
  orbCanvasRef,
  onToggleCollapse,
  onStart,
  startPending,
  startProgress,
}: OrbDockProps) {
  const caption = transcript || reply
  const ringColor = RING_COLORS[orbState]

  return (
    <aside className={`orbDock${collapsed ? ' collapsed' : ''}`} aria-label="Mango orb">
      <div className="orbDockInner glass-panel">
        <button
          type="button"
          className="orbDockToggle"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand orb panel' : 'Collapse orb panel'}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? '›' : '‹'}
        </button>

        {!running ? (
          <div className="orbDockOffline">
            <p className="orbDockOfflineTitle">Mango offline</p>
            <p className="orbDockOfflineSub">{startProgress || 'Start to talk or type.'}</p>
            <button type="button" className="glassBtnPrimary" disabled={startPending} onClick={onStart}>
              {startPending ? 'Starting…' : 'Start Mango'}
            </button>
          </div>
        ) : (
          <>
            <div className={`orbRingWrap orbRingState-${orbState}`} style={{ ['--ring-color' as string]: ringColor }}>
              <div className="orbRing" aria-hidden="true" />
              <div className="legacySphereWrap" ref={orbWrapRef}>
                <canvas ref={orbCanvasRef} className="orbCanvas" aria-hidden="true" />
              </div>
            </div>
            {!collapsed ? (
              <>
                <p className="orbStateLabel">{assistantStateLabel(orbState, running)}</p>
                {caption ? (
                  <p className="orbUtterance" title={caption}>
                    {caption}
                  </p>
                ) : (
                  <p className="orbUtterance muted">Ready when you are.</p>
                )}
              </>
            ) : null}
          </>
        )}
      </div>
    </aside>
  )
}

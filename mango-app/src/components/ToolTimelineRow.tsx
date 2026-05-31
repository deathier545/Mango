import { useState } from 'react'

export type ToolTimelineDetail = {
  label: string
  value: string
}

type ToolTimelineRowProps = {
  timeLabel: string
  tool: string
  risk: string
  statusLabel: string
  durationLabel: string
  failed?: boolean
  details?: ToolTimelineDetail[]
  onRetry?: () => void
}

export function ToolTimelineRow({
  timeLabel,
  tool,
  risk,
  statusLabel,
  durationLabel,
  failed = false,
  details = [],
  onRetry,
}: ToolTimelineRowProps) {
  const [open, setOpen] = useState(false)
  const hasDetails = details.length > 0 || Boolean(onRetry)

  return (
    <div className={`toolTimelineRow${failed ? ' toolFail' : ''}`}>
      <button
        type="button"
        className="toolTimelineSummary"
        onClick={() => hasDetails && setOpen((v) => !v)}
        disabled={!hasDetails}
        aria-expanded={hasDetails ? open : undefined}
      >
        <span className="toolTime">{timeLabel}</span>
        <span className="toolName">{tool}</span>
        <span className={`toolRisk ${risk}`}>{risk}</span>
        <span className="toolDuration">{durationLabel}</span>
        <span className={`toolOk ${failed ? 'bad' : 'good'}`}>{statusLabel}</span>
        {hasDetails ? <span className="toolExpandHint">{open ? '▾' : '▸'}</span> : null}
      </button>
      {open && hasDetails ? (
        <div className="toolTimelineDetails">
          {details.map((d) => (
            <p key={d.label}>
              <span className="toolDetailLabel">{d.label}</span> {d.value}
            </p>
          ))}
          {onRetry ? (
            <button type="button" className="btnSecondary ghostBtn small" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

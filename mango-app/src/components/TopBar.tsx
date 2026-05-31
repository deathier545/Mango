import type { DiscordBridgeStatus, MangoStatus, OrbState } from '../types/ui'
import { assistantStateLabel } from '../lib/format'

type TopBarProps = {
  status: MangoStatus
  orbState: OrbState
  startedLabel: string
  discord: DiscordBridgeStatus
  startPending: boolean
  onStart: () => void
  onStop: () => void
  onRestart: () => void
}

export function TopBar({
  status,
  orbState,
  startedLabel,
  discord,
  startPending,
  onStart,
  onStop,
  onRestart,
}: TopBarProps) {
  const stateLabel = assistantStateLabel(orbState, status.running)

  return (
    <header className="topbar">
      <div className="brand">
        <span className="brandDot" />
        <h1>Mango Console</h1>
      </div>
      <div className="status topbarStatus">
        <span className={`dot ${status.running ? 'on' : 'off'}`} />
        <span>{status.running ? 'Online' : 'Offline'}</span>
        <span className="statusSep" aria-hidden="true">
          ·
        </span>
        <span className={`assistantPill state-${orbState}`} title="Voice assistant state">
          {stateLabel}
        </span>
        <span className="statusSep" aria-hidden="true">
          ·
        </span>
        {discord.reachable ? (
          <span
            className={`bridgePill ${discord.ok ? 'ok' : 'warn'}`}
            title={
              discord.musicOn
                ? `Discord bridge · music on${discord.ownerVoice ? ` · ${discord.ownerVoice}` : ''}`
                : `Discord bridge${discord.ownerVoice ? ` · ${discord.ownerVoice}` : ''}`
            }
          >
            Discord {discord.musicOn ? '· music' : discord.ok ? '· ready' : '· idle'}
          </span>
        ) : (
          <span className="bridgePill missing" title="Start scripts/start-mango-discord.ps1 for call music">
            Discord offline
          </span>
        )}
        <span className="meta topbarStarted" title="Session started">
          {startedLabel}
        </span>
      </div>
      <div className="controls topbarControls">
        <button type="button" className="btnPrimary" onClick={onStart} disabled={status.running || startPending}>
          {startPending ? 'Starting…' : 'Start'}
        </button>
        <button type="button" className="btnSecondary" onClick={onRestart} disabled={startPending}>
          Restart
        </button>
        <button type="button" className="btnDanger" onClick={onStop} disabled={!status.running || startPending}>
          Stop
        </button>
      </div>
    </header>
  )
}

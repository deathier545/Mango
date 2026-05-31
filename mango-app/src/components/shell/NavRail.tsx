import type { AppZone } from '../../types/ui'
import { ZoneIcon } from './NavIcons'

const ZONES: {
  id: AppZone
  label: string
  hint: string
  shortcut: string
}[] = [
  { id: 'command', label: 'Command', hint: 'Conversation & compose', shortcut: 'Ctrl+1' },
  { id: 'intelligence', label: 'Smart', hint: 'Memory, routines, badges', shortcut: 'Ctrl+2' },
  { id: 'diagnostics', label: 'Diagnostics', hint: 'Metrics, voice log, system', shortcut: 'Ctrl+3' },
  { id: 'config', label: 'Config', hint: 'Settings & diagnostics export', shortcut: 'Ctrl+4' },
]

type NavRailProps = {
  activeZone: AppZone
  onZone: (zone: AppZone) => void
}

export function NavRail({ activeZone, onZone }: NavRailProps) {
  return (
    <nav className="navRail" aria-label="Main navigation">
      <div className="navRailBrand" aria-hidden="true">
        M
      </div>
      {ZONES.map((zone) => (
        <button
          key={zone.id}
          type="button"
          className={activeZone === zone.id ? 'navRailBtn active' : 'navRailBtn'}
          title={`${zone.label} — ${zone.hint} (${zone.shortcut})`}
          aria-current={activeZone === zone.id ? 'page' : undefined}
          aria-label={zone.label}
          onClick={() => onZone(zone.id)}
        >
          <span className="navRailIcon" aria-hidden="true">
            <ZoneIcon zone={zone.id} />
          </span>
          <span className="navRailLabel">{zone.label}</span>
        </button>
      ))}
    </nav>
  )
}

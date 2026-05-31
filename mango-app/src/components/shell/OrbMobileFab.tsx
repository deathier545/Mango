import type { OrbState } from '../../types/ui'
import { assistantStateLabel } from '../../lib/format'

type OrbMobileFabProps = {
  orbState: OrbState
  running: boolean
  onPress: () => void
}

export function OrbMobileFab({ orbState, running, onPress }: OrbMobileFabProps) {
  return (
    <button
      type="button"
      className={`orbMobileFab state-${orbState}`}
      aria-label={assistantStateLabel(orbState, running)}
      title={assistantStateLabel(orbState, running)}
      onClick={onPress}
    >
      <span className="orbFabDot" aria-hidden="true" />
    </button>
  )
}

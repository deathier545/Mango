import { useRef, type RefObject } from 'react'

import { useOrbCanvas } from '../hooks/useOrbCanvas'
import { AMBER_ORB_TARGETS, ORB_TARGETS } from '../orb/orbConfig'
import type { OrbState } from '../types/ui'

type DuoOrbUnitProps = {
  label: string
  orbState: OrbState
  enabled: boolean
  variant: 'mango' | 'amber'
  orbWrapRef: RefObject<HTMLDivElement | null>
  orbCanvasRef: RefObject<HTMLCanvasElement | null>
  audioLevelRef: RefObject<number>
}

function DuoOrbUnit({
  label,
  orbState,
  enabled,
  variant,
  orbWrapRef,
  orbCanvasRef,
  audioLevelRef,
}: DuoOrbUnitProps) {
  const orbStateRef = useRef<OrbState>(orbState)
  orbStateRef.current = orbState
  const targets = variant === 'amber' ? AMBER_ORB_TARGETS : ORB_TARGETS
  useOrbCanvas(enabled, orbState, orbWrapRef, orbCanvasRef, audioLevelRef, orbStateRef, targets)

  return (
    <div className={`duoOrbUnit state-${orbState} duoOrbUnit-${variant}`}>
      <p className="duoOrbLabel">{label}</p>
      <div className={`legacySphereWrap duoSphereWrap duoSphereWrap-${variant}`} ref={orbWrapRef}>
        <canvas ref={orbCanvasRef} className="orbCanvas" aria-hidden="true" />
      </div>
      <p className="duoOrbCaption" aria-live="polite">
        {orbState === 'thinking' ? 'Thinking…' : orbState === 'speaking' ? 'Speaking' : 'Ready'}
      </p>
    </div>
  )
}

export type DuoLine = {
  speaker: 'mango' | 'amber'
  text: string
}

type DuoSceneProps = {
  enabled: boolean
  mangoState: OrbState
  amberState: OrbState
  topic: string
  rounds: number
  running: boolean
  lines: DuoLine[]
  onTopicChange: (topic: string) => void
  onRoundsChange: (rounds: number) => void
  onStart: () => void
  onExit: () => void
  mangoAudioRef: RefObject<number>
  amberAudioRef: RefObject<number>
}

export function DuoScene({
  enabled,
  mangoState,
  amberState,
  topic,
  rounds,
  running,
  lines,
  onTopicChange,
  onRoundsChange,
  onStart,
  onExit,
  mangoAudioRef,
  amberAudioRef,
}: DuoSceneProps) {
  const mangoWrapRef = useRef<HTMLDivElement | null>(null)
  const mangoCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const amberWrapRef = useRef<HTMLDivElement | null>(null)
  const amberCanvasRef = useRef<HTMLCanvasElement | null>(null)

  return (
    <div className="duoScene">
      <div className="duoOrbRow">
        <DuoOrbUnit
          label="Mango"
          variant="mango"
          orbState={mangoState}
          enabled={enabled}
          orbWrapRef={mangoWrapRef}
          orbCanvasRef={mangoCanvasRef}
          audioLevelRef={mangoAudioRef}
        />
        <DuoOrbUnit
          label="Amber"
          variant="amber"
          orbState={amberState}
          enabled={enabled}
          orbWrapRef={amberWrapRef}
          orbCanvasRef={amberCanvasRef}
          audioLevelRef={amberAudioRef}
        />
      </div>

      <div className="duoControls panel">
        <p className="panelSub">
          Duo panel — Mango and Amber take turns discussing a topic you choose. Mango opens; Amber responds.
        </p>
        <label className="duoTopicLabel">
          Topic
          <input
            className="modelInput"
            value={topic}
            onChange={(e) => onTopicChange(e.target.value)}
            placeholder="e.g. Should AI assistants have personalities?"
            disabled={running}
          />
        </label>
        <label className="duoTopicLabel">
          Rounds (each = Mango + Amber)
          <select
            className="modelInput"
            value={rounds}
            onChange={(e) => onRoundsChange(Number(e.target.value))}
            disabled={running}
          >
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <div className="duoControlActions">
          <button type="button" className="btnPrimary" onClick={onStart} disabled={running || !topic.trim()}>
            {running ? 'Conversation running…' : 'Start duo conversation'}
          </button>
          <button type="button" className="btnSecondary" onClick={onExit} disabled={running}>
            Solo Mango
          </button>
        </div>
      </div>

      {lines.length > 0 ? (
        <aside className="duoTranscript" aria-label="Duo conversation transcript">
          {lines.map((line, idx) => (
            <p key={`${line.speaker}-${idx}`}>
              <span className={`liveLabel ${line.speaker === 'amber' ? 'liveLabelAmber' : ''}`}>
                {line.speaker === 'amber' ? 'Amber' : 'Mango'}
              </span>{' '}
              {line.text}
            </p>
          ))}
        </aside>
      ) : null}
    </div>
  )
}

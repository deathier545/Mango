import { useRef, type RefObject } from 'react'

import { duoUnavailableMessage } from '../lib/mango-bridge'

import { useOrbCanvas } from '../hooks/useOrbCanvas'
import { AMBER_ORB_TARGETS, ORB_TARGETS } from '../orb/orbConfig'
import type { OrbState } from '../types/ui'

const DUO_TOPIC_CHIPS = [
  'AI personalities',
  'Plan my day',
  'Gaming strategy',
  'Debate both sides',
  'Explain a topic',
  'Relationship advice',
] as const

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
  duoAvailable: boolean
  mangoState: OrbState
  amberState: OrbState
  topic: string
  rounds: number
  speak: boolean
  running: boolean
  duoBlocked: boolean
  lines: DuoLine[]
  onTopicChange: (topic: string) => void
  onRoundsChange: (rounds: number) => void
  onSpeakChange: (speak: boolean) => void
  onStart: () => void
  onStop: () => void
  onExit: () => void
  mangoAudioRef: RefObject<number>
  amberAudioRef: RefObject<number>
}

export function DuoScene({
  enabled,
  duoAvailable,
  mangoState,
  amberState,
  topic,
  rounds,
  speak,
  running,
  duoBlocked,
  lines,
  onTopicChange,
  onRoundsChange,
  onSpeakChange,
  onStart,
  onStop,
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
      <p className="duoFlowHint" role="status">
        Mango opens → Amber responds → repeats for {rounds} round{rounds === 1 ? '' : 's'}
      </p>

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
          Mango and Amber discuss a topic you choose. Mango speaks first; Amber responds each round.
        </p>
        {!duoAvailable ? (
          <p className="duoBlockedNote" role="alert">
            {duoUnavailableMessage()}
          </p>
        ) : null}
        {duoBlocked ? (
          <p className="duoBlockedNote" role="alert">
            Duo works best when Mango is idle. Wait for voice playback to finish or stop Mango first.
          </p>
        ) : null}
        <label className="duoTopicLabel">
          Topic
          <input
            className="modelInput"
            value={topic}
            onChange={(e) => onTopicChange(e.target.value)}
            placeholder="e.g. Should AI assistants have personalities?"
            disabled={running}
            maxLength={300}
          />
        </label>
        <div className="duoTopicChips">
          {DUO_TOPIC_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              className="btnSecondary duoTopicChip"
              disabled={running}
              onClick={() => onTopicChange(chip)}
            >
              {chip}
            </button>
          ))}
        </div>
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
        <label className="duoCheck">
          <input
            type="checkbox"
            checked={speak}
            onChange={(e) => onSpeakChange(e.target.checked)}
            disabled={running}
          />
          Speak out loud
        </label>
        <div className="duoControlActions">
          <button
            type="button"
            className="btnPrimary"
            onClick={onStart}
            disabled={running || duoBlocked || !duoAvailable || !topic.trim()}
          >
            {running ? 'Conversation running…' : 'Start duo conversation'}
          </button>
          <button type="button" className="btnDanger" onClick={onStop} disabled={!running}>
            Stop duo
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

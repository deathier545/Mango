import type { RefObject } from 'react'

import { HUD_QUICK_PROMPTS } from '../lib/quickPrompts'

import type { OrbState, ToolEvent, TurnMetrics } from '../types/ui'

import { cleanUiText, orbCaption } from '../lib/format'



type MangoHudProps = {

  orbState: OrbState

  running: boolean

  transcript: string

  reply: string

  globeVisible: boolean

  globeLabel: string

  hasGlobeUrl: boolean

  orbWrapRef: RefObject<HTMLDivElement | null>

  orbCanvasRef: RefObject<HTMLCanvasElement | null>

  mapHostRef: RefObject<HTMLDivElement | null>

  onBackFromMap: () => void

  onOpenExternal: () => void

  onResumeMap: () => void

  onStart: () => void

  startPending: boolean
  startProgress: string
  turnMetrics: TurnMetrics | null
  latestToolEvent: ToolEvent | null

  onQuickPrompt: (text: string) => void

}



export function MangoHud({

  orbState,

  running,

  transcript,

  reply,

  globeVisible,

  globeLabel,

  hasGlobeUrl,

  orbWrapRef,

  orbCanvasRef,

  mapHostRef,

  onBackFromMap,

  onOpenExternal,

  onResumeMap,

  onStart,

  startPending,
  startProgress,
  turnMetrics,
  latestToolEvent,

  onQuickPrompt,

}: MangoHudProps) {

  const showMap = globeVisible

  const caption = orbCaption(orbState, running)

  const hasLiveStrip = running && Boolean(transcript || reply) && !showMap

  const hasQuickBar = running && !showMap



  const hudClass = [

    'hudScreen',

    showMap ? 'mapOpen' : '',

    hasLiveStrip ? 'hasLiveStrip' : '',

    hasQuickBar ? 'hasQuickBar' : '',

  ]

    .filter(Boolean)

    .join(' ')



  return (

    <section className={hudClass} aria-label="Mango voice display">

      <div className="hudDecor" aria-hidden="true">

        <div className="hudFrame" />

        <div className="hudGrid" />

        <div className="hudScanlines" />

        <span className="hudCorner tl" />

        <span className="hudCorner tr" />

        <span className="hudCorner bl" />

        <span className="hudCorner br" />

      </div>



      {hasQuickBar ? (

        <div className="mangoQuickActions">

          {hasGlobeUrl ? (

            <button type="button" className="btnSecondary" onClick={onResumeMap}>

              Resume map

            </button>

          ) : null}

          {HUD_QUICK_PROMPTS.map((q) => (

            <button key={q.label} type="button" className="btnSecondary" onClick={() => onQuickPrompt(q.prompt)}>

              {q.label}

            </button>

          ))}

        </div>

      ) : null}



      <div className="hudSceneStack">

        <div className={`sceneLayer mapScene ${showMap ? 'sceneVisible' : ''}`}>

          <div className="mapHeader">

            <span>{globeLabel || 'Map'}</span>

            <div className="mapHeaderActions">

              <button type="button" className="btnSecondary" onClick={onOpenExternal}>

                Open external

              </button>

              <button type="button" className="btnSecondary" onClick={onBackFromMap}>

                Back to Mango

              </button>

            </div>

          </div>

          <div className="mapFrame mapFrameFallback" ref={mapHostRef} aria-label={globeLabel || 'Mango map'} />

        </div>



        <div className={`sceneLayer orbScene state-${orbState} ${showMap ? '' : 'sceneVisible'}`}>

          {!running && !showMap ? (

            <div className="offlineOverlay">

              <p className="offlineTitle">Mango is offline</p>

              <p className="offlineBody">Start voice to use wake word, push-to-talk (Alt+W), and tools.</p>

              <button type="button" className="btnPrimary btnLarge" onClick={onStart} disabled={startPending}>

                {startPending ? 'Starting Mango…' : 'Start Mango'}

              </button>
              {startPending && startProgress ? <p className="offlineBody">{startProgress}</p> : null}

            </div>

          ) : null}

          <div className="legacySphereWrap" ref={orbWrapRef}>

            <canvas ref={orbCanvasRef} className="orbCanvas" aria-hidden="true" />

          </div>

          <p className="orbCaption" aria-live="polite">

            {caption}

          </p>

        </div>

      </div>



      {hasLiveStrip ? (

        <aside className="liveStrip" aria-label="Latest voice turn" role="status" aria-live="polite" aria-atomic="false">

          {transcript ? (

            <p>

              <span className="liveLabel">You</span> {cleanUiText(transcript)}

            </p>

          ) : null}

          {reply ? (

            <p>

              <span className="liveLabel">Mango</span> {cleanUiText(reply)}

            </p>

          ) : null}
          {latestToolEvent ? (
            <p className="liveAux">
              <span className="liveLabel">Tool</span> {latestToolEvent.tool} {latestToolEvent.event.replace('tool_', '')}
            </p>
          ) : null}
          {turnMetrics ? (
            <p className="liveAux">
              <span className="liveLabel">Latency</span>
              STT {turnMetrics.sttS?.toFixed(2) ?? '—'}s · LLM {turnMetrics.llmS?.toFixed(2) ?? '—'}s · TTS{' '}
              {turnMetrics.ttsS?.toFixed(2) ?? '—'}s
            </p>
          ) : null}

        </aside>

      ) : null}

    </section>

  )

}


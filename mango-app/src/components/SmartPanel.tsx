import { useCallback, useEffect, useState } from 'react'

import { SMART_ACTIONS } from '../lib/smartActions'

import type { BadgeCategory, MemoryCard, MangoBadge, SmartSnapshot, TimelineEntry } from '../types/ui'

import { ToolTimelineRow } from './ToolTimelineRow'



const QUICK_ACTIONS = SMART_ACTIONS.filter(

  (a) => a.category === 'routine' || a.category === 'brief' || a.category === 'clipboard',

)



type SmartTab = 'quick' | 'memory' | 'routines' | 'timeline' | 'badges'

const SMART_TABS: { id: SmartTab; label: string }[] = [
  { id: 'quick', label: 'Quick' },
  { id: 'memory', label: 'Memory' },
  { id: 'routines', label: 'Routines' },
  { id: 'badges', label: 'Badges' },
  { id: 'timeline', label: 'Timeline' },
]

const BADGE_CATEGORIES: { id: BadgeCategory; label: string }[] = [
  { id: 'memory', label: 'Memory' },
  { id: 'skills', label: 'Skills' },
  { id: 'routines', label: 'Routines' },
  { id: 'tools', label: 'Tools' },
  { id: 'discord', label: 'Discord' },
  { id: 'integrations', label: 'Integrations' },
  { id: 'continuity', label: 'Continuity' },
  { id: 'smart', label: 'Smart' },
  { id: 'voice', label: 'Voice' },
]

function badgeProgressPct(badge: MangoBadge): number {
  if (!badge.progress || badge.progress.target <= 0) return badge.unlocked ? 100 : 0
  return Math.min(100, Math.round((badge.progress.current / badge.progress.target) * 100))
}



type SmartPanelProps = {

  onNotify: (msg: string, kind?: 'info' | 'success' | 'error') => void

  onSendPrompt: (text: string) => void

}



export function SmartPanel({ onNotify, onSendPrompt }: SmartPanelProps) {

  const [tab, setTab] = useState<SmartTab>('quick')

  const [snapshot, setSnapshot] = useState<SmartSnapshot | null>(null)

  const [brief, setBrief] = useState('')

  const [loading, setLoading] = useState(false)

  const [cardTitle, setCardTitle] = useState('')

  const [cardContent, setCardContent] = useState('')

  const [cardCategory, setCardCategory] = useState<MemoryCard['category']>('fact')

  const [captureText, setCaptureText] = useState('')

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)



  const refresh = useCallback(async () => {

    if (!window.mango?.smartSnapshot) return

    setLoading(true)

    try {

      const r = await window.mango.smartSnapshot()

      if (r.ok && r.data) setSnapshot(r.data as SmartSnapshot)

      else onNotify(r.error || 'Could not load smart data', 'error')

    } catch (e) {

      onNotify(String(e), 'error')

    } finally {

      setLoading(false)

    }

  }, [onNotify])



  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => window.clearTimeout(timer)

  }, [refresh])



  const loadBrief = async () => {

    if (!window.mango?.smartBrief) return

    const r = await window.mango.smartBrief()

    if (r.ok) {

      setBrief(r.text || '')

      onNotify('Briefing ready', 'success')

    } else onNotify(r.error || 'Brief failed', 'error')

  }



  const addCard = async () => {

    if (!cardContent.trim()) return

    const r = await window.mango.smartCardAdd({

      title: cardTitle || 'Note',

      content: cardContent,

      category: cardCategory,

    })

    if (r.ok) {

      setCardTitle('')

      setCardContent('')

      onNotify('Memory card saved', 'success')

      void refresh()

    } else onNotify(r.error || 'Save failed', 'error')

  }



  const deleteCard = async (id: string) => {

    const r = await window.mango.smartCardDelete(id)

    setConfirmDeleteId(null)

    if (r.ok) {

      onNotify('Memory deleted', 'info')

      void refresh()

    }

  }



  const addCapture = async () => {

    if (!captureText.trim()) return

    const r = await window.mango.smartInboxAdd(captureText)

    if (r.ok) {

      setCaptureText('')

      onNotify('Captured', 'success')

      void refresh()

    }

  }



  const timeline = snapshot?.timeline ?? []
  const cards = snapshot?.cards ?? []
  const routines = snapshot?.routines ?? []
  const badgeSnapshot = snapshot?.badges
  const badges = badgeSnapshot?.badges ?? []
  const badgeSummary = badgeSnapshot?.summary



  return (

    <section className="smartShell">

      <header className="smartShellHead panel">

        <div className="smartPanelHead">

          <h2>Smart</h2>

          <button type="button" className="btnSecondary" onClick={() => void refresh()} disabled={loading}>

            Refresh

          </button>

        </div>

        <nav className="smartSubTabs" aria-label="Smart sections">

          {SMART_TABS.map((t) => (

            <button

              key={t.id}

              type="button"

              className={tab === t.id ? 'smartSubTab active' : 'smartSubTab'}

              onClick={() => setTab(t.id)}

              aria-current={tab === t.id ? 'page' : undefined}

            >

              {t.label}

            </button>

          ))}

        </nav>

      </header>



      {tab === 'quick' ? (

        <section className="panel smartSection">

          <h3>Quick actions</h3>

          <p className="metricMeta">One-tap routines and helpers — same as Ctrl+K palette.</p>

          <div className="smartActionGrid">

            {QUICK_ACTIONS.map((action) => (

              <button

                key={action.id}

                type="button"

                className="smartActionTile"

                onClick={() => {

                  if (action.prompt) onSendPrompt(action.prompt)

                }}

                disabled={!action.prompt}

              >

                <span className="smartActionLabel">{action.label}</span>

                <span className="smartActionHint">{action.hint}</span>

              </button>

            ))}

          </div>



          <h3>Daily briefing</h3>

          <p className="metricMeta">

            Generate loads text here locally. Ask Mango sends the same request in chat.

          </p>

          <div className="smartRow">

            <button type="button" className="btnPrimary" onClick={() => void loadBrief()}>

              Generate locally

            </button>

            <button type="button" className="btnSecondary" onClick={() => onSendPrompt('Give me my daily briefing.')}>

              Ask Mango in chat

            </button>

          </div>

          {brief ? <pre className="briefBox">{brief}</pre> : null}

        </section>

      ) : null}



      {tab === 'memory' ? (

        <section className="panel smartSection">

          <h3>Memory cards</h3>

          <div className="smartForm">

            <label>

              Title

              <input value={cardTitle} onChange={(e) => setCardTitle(e.target.value)} />

            </label>

            <label>

              Category

              <select value={cardCategory} onChange={(e) => setCardCategory(e.target.value as MemoryCard['category'])}>

                <option value="person">person</option>

                <option value="preference">preference</option>

                <option value="device">device</option>

                <option value="fact">fact</option>

                <option value="task">task</option>

              </select>

            </label>

            <label>

              Memory

              <textarea

                value={cardContent}

                onChange={(e) => setCardContent(e.target.value)}

                rows={3}

                placeholder="What should Mango remember?"

              />

            </label>

            <button type="button" className="btnPrimary" onClick={() => void addCard()}>

              Save card

            </button>

          </div>

          <ul className="cardList">

            {cards.length === 0 ? <li className="empty">No cards yet.</li> : null}

            {cards.map((c) => (

              <li key={c.id} className="cardItem">

                <div className="cardItemHead">

                  <strong>{c.title}</strong>

                  <span className="pill">{c.category}</span>

                  {confirmDeleteId === c.id ? (

                    <span className="cardDeleteConfirm">

                      <span className="cardDeletePrompt">Delete permanently?</span>

                      <button type="button" className="btnDanger ghostBtn small" onClick={() => void deleteCard(c.id)}>

                        Delete

                      </button>

                      <button type="button" className="btnSecondary ghostBtn small" onClick={() => setConfirmDeleteId(null)}>

                        Cancel

                      </button>

                    </span>

                  ) : (

                    <button

                      type="button"

                      className="btnSecondary ghostBtn small"

                      onClick={() => setConfirmDeleteId(c.id)}

                    >

                      Delete

                    </button>

                  )}

                </div>

                <p>{c.content}</p>

              </li>

            ))}

          </ul>



          <h3>Quick capture</h3>

          <p className="metricMeta">Inbox notes for later — not the same as memory cards.</p>

          <div className="smartForm">

            <label>

              Note

              <textarea

                value={captureText}

                onChange={(e) => setCaptureText(e.target.value)}

                rows={2}

                placeholder="Remember this for later…"

              />

            </label>

            <button type="button" className="btnPrimary" onClick={() => void addCapture()}>

              Add to inbox

            </button>

          </div>

        </section>

      ) : null}



      {tab === 'routines' ? (

        <section className="panel smartSection">

          <h3>Saved routines</h3>

          <p className="metricMeta">From your Mango smart store — night mode, focus, Discord flows.</p>

          <ul className="routineList">

            {routines.length === 0 ? <li className="empty routineEmpty">No routines loaded yet.</li> : null}

            {routines.map((r) => (

              <li key={r.id} className="routineCard">

                <div className="routineCardBody">

                  <strong className="routineCardTitle">{r.name}</strong>

                  <p className="routineCardDesc">{r.description}</p>

                  <code className="routineCardId">{r.id}</code>

                </div>

                <button

                  type="button"

                  className="btnPrimary routineRunBtn"

                  onClick={() => onSendPrompt(`Run routine ${r.id}.`)}

                >

                  Run

                </button>

              </li>

            ))}

          </ul>

        </section>

      ) : null}



      {tab === 'badges' ? (
        <section className="panel smartSection badgeSection">
          <div className="badgeSummaryHead">
            <div>
              <h3>Mango's badges</h3>
              <p className="metricMeta">
                Milestones Mango has unlocked on this PC — memory, skills, routines, tools, and more.
              </p>
            </div>
            {badgeSummary ? (
              <div className="badgeSummaryStat" aria-label="Mango badge progress">
                <span className="badgeSummaryCount">
                  {badgeSummary.unlocked}/{badgeSummary.total}
                </span>
                <span className="badgeSummaryLabel">Mango unlocked</span>
                <div className="badgeSummaryBar" aria-hidden="true">
                  <span className="badgeSummaryFill" style={{ width: `${badgeSummary.percent}%` }} />
                </div>
              </div>
            ) : null}
          </div>

          {badges.length === 0 ? (
            <p className="empty">No badge data yet — hit Refresh.</p>
          ) : (
            BADGE_CATEGORIES.map((cat) => {
            const rows = badges.filter((b) => b.category === cat.id)
            if (rows.length === 0) return null
            return (
              <div key={cat.id} className="badgeCategoryBlock">
                <h4 className="badgeCategoryTitle">{cat.label}</h4>
                <div className="badgeGrid">
                  {rows.map((badge) => {
                    const pct = badgeProgressPct(badge)
                    return (
                      <article
                        key={badge.id}
                        className={badge.unlocked ? 'badgeCard unlocked' : 'badgeCard locked'}
                        aria-label={`${badge.title}${badge.unlocked ? ', unlocked' : ', locked'}`}
                      >
                        <div className="badgeIcon" aria-hidden="true">
                          {badge.icon}
                        </div>
                        <div className="badgeBody">
                          <strong className="badgeTitle">{badge.title}</strong>
                          <p className="badgeDesc">{badge.description}</p>
                          {!badge.unlocked && badge.hint ? (
                            <p className="badgeHint">{badge.hint}</p>
                          ) : null}
                          {!badge.unlocked && badge.progress ? (
                            <div className="badgeProgressWrap">
                              <div className="badgeProgressBar" aria-hidden="true">
                                <span className="badgeProgressFill" style={{ width: `${pct}%` }} />
                              </div>
                              <span className="badgeProgressText">
                                {badge.progress.current}/{badge.progress.target}
                              </span>
                            </div>
                          ) : null}
                        </div>
                        <span className="badgeStatus">{badge.unlocked ? 'Unlocked' : 'Locked'}</span>
                      </article>
                    )
                  })}
                </div>
              </div>
            )
          })
          )}
        </section>
      ) : null}

      {tab === 'timeline' ? (
        <section className="panel smartSection">
          <h3>Tool timeline</h3>
          <p className="metricMeta">Tap a row for details. Newest first.</p>

          <div className="tools toolTimelineList">

            {timeline.length === 0 ? <p className="empty">No tool events yet.</p> : null}

            {[...timeline].reverse().map((item: TimelineEntry, idx) => {

              const failed = item.ok === false

              const details = [

                { label: 'Risk:', value: item.risk || '—' },

                { label: 'Event:', value: failed ? 'failed' : 'completed' },

                ...(item.correlation_id

                  ? [{ label: 'Correlation:', value: item.correlation_id }]

                  : []),

                ...(item.error_code ? [{ label: 'Error code:', value: item.error_code }] : []),

                ...(item.result_preview

                  ? [{ label: 'Preview:', value: item.result_preview }]

                  : []),

              ]

              return (

                <ToolTimelineRow

                  key={`${item.ts}-${idx}`}

                  timeLabel={new Date((item.ts || 0) * 1000).toLocaleTimeString()}

                  tool={item.tool}

                  risk={item.risk}

                  statusLabel={failed ? 'fail' : 'ok'}

                  durationLabel={item.duration_ms != null ? `${item.duration_ms}ms` : '—'}

                  failed={failed}

                  details={details}

                  onRetry={

                    failed && item.result_preview

                      ? () =>

                          onSendPrompt(

                            `Retry the last failed ${item.tool} step and tell me what happened.`,

                          )

                      : undefined

                  }

                />

              )

            })}

          </div>

        </section>

      ) : null}

    </section>

  )

}


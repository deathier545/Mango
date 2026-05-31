import { useMemo, useState } from 'react'
import type { LogEntry, TimelineItem } from '../types/ui'
import { cleanUiText } from '../lib/format'
import { CopyButton } from './CopyButton'

type ConversationPanelProps = {
  transcript: string
  reply: string
  timeline: TimelineItem[]
  logs: LogEntry[]
}

export function ConversationPanel({ transcript, reply, timeline, logs }: ConversationPanelProps) {
  const [logQuery, setLogQuery] = useState('')
  const [newestFirst, setNewestFirst] = useState(true)
  const sorted = useMemo(
    () => [...timeline].sort((a, b) => (newestFirst ? b.seq - a.seq : a.seq - b.seq)),
    [timeline, newestFirst],
  )
  const filteredLogs = useMemo(() => {
    const q = logQuery.trim().toLowerCase()
    const reversed = [...logs].reverse()
    if (!q) return reversed
    return reversed.filter((e) => cleanUiText(e.line).toLowerCase().includes(q))
  }, [logs, logQuery])

  return (
    <section className="contentGrid">
      <section className="panel">
        <header className="panelHead">
          <div>
            <h2>Voice log</h2>
            <p className="panelSub">Transcripts from wake word and push-to-talk (Alt+W). Use Chat for typed messages.</p>
          </div>
          <button type="button" className="btnSecondary" onClick={() => setNewestFirst((v) => !v)}>
            {newestFirst ? 'Show oldest first' : 'Show newest first'}
          </button>
        </header>
        <h3>Last transcript</h3>
        <p className="block">{transcript ? cleanUiText(transcript) : 'No transcript yet.'}</p>
        <h3>Last reply</h3>
        <p className="block">{reply ? cleanUiText(reply) : 'No reply yet.'}</p>
        <h3>Timeline</h3>
        <div className="timeline" role="log" aria-live="polite" aria-relevant="additions text">
          {sorted.length === 0 ? (
            <p className="empty">No voice turns yet.</p>
          ) : (
            sorted.map((item) => (
              <div key={item.id} className={`turn ${item.role}`}>
                <div className="turnHead">
                  <span className="turnMeta">
                    {item.role === 'user' ? 'You' : 'Mango'} · {new Date(item.ts).toLocaleTimeString()}
                  </span>
                  <CopyButton text={cleanUiText(item.text)} />
                </div>
                <span>{cleanUiText(item.text)}</span>
              </div>
            ))
          )}
        </div>
      </section>
      <section className="panel">
        <header className="panelHead logsHead">
          <div>
            <h2>System logs</h2>
            <p className="panelSub">Python stdout/stderr from the Mango process.</p>
          </div>
          <input
            className="logSearch"
            type="search"
            placeholder="Search logs…"
            value={logQuery}
            onChange={(e) => setLogQuery(e.target.value)}
            aria-label="Search logs"
          />
        </header>
        <div className="logs" role="log" aria-live="polite" aria-relevant="additions text">
          {filteredLogs.length === 0 ? (
            <p className="empty">{logQuery ? 'No matching log lines.' : 'No logs yet.'}</p>
          ) : (
            filteredLogs.map((entry, idx) => (
              <div key={`${entry.ts}-${idx}`} className={`line ${entry.kind}`}>
                <span className="time">{new Date(entry.ts).toLocaleTimeString()}</span>
                <span>{cleanUiText(entry.line)}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </section>
  )
}

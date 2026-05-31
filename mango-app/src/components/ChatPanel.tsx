import type { RefObject } from 'react'
import { CHAT_QUICK_PROMPTS } from '../lib/quickPrompts'
import type { TimelineItem } from '../types/ui'
import { cleanUiText } from '../lib/format'
import { CopyButton } from './CopyButton'

type ChatPanelProps = {
  timeline: TimelineItem[]
  chatInput: string
  manualSending: boolean
  chatFeedRef: RefObject<HTMLDivElement | null>
  chatInputRef: RefObject<HTMLTextAreaElement | null>
  onInput: (value: string) => void
  onSend: () => void
  onClear: () => void
  onPrompt: (text: string) => void
  onFeedScroll: (el: HTMLDivElement) => void
}

export function ChatPanel({
  timeline,
  chatInput,
  manualSending,
  chatFeedRef,
  chatInputRef,
  onInput,
  onSend,
  onClear,
  onPrompt,
  onFeedScroll,
}: ChatPanelProps) {
  return (
    <section className="chatLayout panel">
      <header className="panelHead">
        <div>
          <h2>Chat</h2>
          <p className="panelSub">
            Typed messages to Mango (separate from wake/PTT in Voice log). Enter to send · Shift+Enter for newline.
          </p>
        </div>
      </header>
      <div
        className="chatFeed"
        ref={chatFeedRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={(e) => onFeedScroll(e.currentTarget)}
      >
        {timeline.length === 0 ? (
          <p className="empty">No messages yet. Type below to chat with Mango.</p>
        ) : (
          timeline.slice(-200).map((item) => (
            <div
              key={item.id}
              className={`chatBubble ${item.role}${item.pending ? ' pending' : ''}`}
              aria-busy={item.pending ? true : undefined}
            >
              <div className="chatBubbleHead">
                <span className="chatMeta">
                  {item.role === 'user' ? 'You' : 'Mango'} · {new Date(item.ts).toLocaleTimeString()}
                </span>
                {!item.pending ? <CopyButton text={cleanUiText(item.text)} /> : null}
              </div>
              <p>{item.pending ? <span className="typingDots">Mango is thinking</span> : cleanUiText(item.text)}</p>
            </div>
          ))
        )}
      </div>
      <footer className="chatFooter">
        <div className="chatInputCard">
          <div className="chatQuickPrompts" aria-label="Quick prompts">
            {CHAT_QUICK_PROMPTS.map((q) => (
              <button key={q.label} type="button" className="btnSecondary" onClick={() => onPrompt(q.prompt)}>
                {q.label}
              </button>
            ))}
          </div>
          <div className="chatComposer">
            <textarea
              ref={chatInputRef}
              value={chatInput}
              onChange={(e) => onInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              placeholder="Type to Mango… (Enter to send, Shift+Enter for newline)"
              rows={2}
              disabled={manualSending}
            />
            <div className="chatActions">
              <button
                type="button"
                className="btnSecondary"
                onClick={onClear}
                disabled={manualSending || timeline.length === 0}
              >
                Clear chat
              </button>
              <button type="button" className="btnPrimary" onClick={onSend} disabled={manualSending || !chatInput.trim()}>
                {manualSending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      </footer>
    </section>
  )
}

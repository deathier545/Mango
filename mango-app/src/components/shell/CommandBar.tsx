import { useEffect } from 'react'
import type { RefObject } from 'react'
import { CHAT_QUICK_PROMPTS } from '../../lib/quickPrompts'

type CommandBarProps = {
  value: string
  sending: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  onChange: (value: string) => void
  onSend: () => void
  onPrompt: (text: string) => void
  assistantState: string
}

export function CommandBar({
  value,
  sending,
  inputRef,
  onChange,
  onSend,
  onPrompt,
  assistantState,
}: CommandBarProps) {
  const resize = () => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  useEffect(() => {
    resize()
  }, [value, inputRef])

  return (
    <footer className="commandBar glass-panel">
      <div className="commandBarPrompts">
        {CHAT_QUICK_PROMPTS.slice(0, 4).map((item) => (
          <button
            key={item.label}
            type="button"
            className="commandChip"
            disabled={sending}
            onClick={() => onPrompt(item.prompt)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="commandBarRow">
        <textarea
          ref={inputRef}
          className="commandInput"
          rows={1}
          placeholder="Ask Mango anything…"
          value={value}
          disabled={sending}
          aria-label="Message Mango"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
        />
        <button
          type="button"
          className="glassBtnPrimary commandSend"
          disabled={sending || !value.trim()}
          onClick={onSend}
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
      <p className="commandHint">
        Enter to send · Shift+Enter newline · Ctrl+K commands · {assistantState}
        {sending ? ' · Mango is thinking…' : ''}
      </p>
    </footer>
  )
}

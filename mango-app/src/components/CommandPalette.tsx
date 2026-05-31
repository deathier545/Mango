import { useEffect, useMemo, useState } from 'react'
import {
  buildPaletteCommands,
  CATEGORY_LABELS,
  type CommandCategory,
  type PaletteCommand,
  type PaletteContext,
} from '../lib/commandRegistry'

type CommandPaletteProps = {
  open: boolean
  onClose: () => void
  paletteContext: PaletteContext
  onRunCommand: (command: PaletteCommand) => void
}

export function CommandPalette({ open, onClose, paletteContext, onRunCommand }: CommandPaletteProps) {
  if (!open) return null
  return (
    <CommandPaletteDialog onClose={onClose} paletteContext={paletteContext} onRunCommand={onRunCommand} />
  )
}

type CommandPaletteDialogProps = Omit<CommandPaletteProps, 'open'>

function CommandPaletteDialog({ onClose, paletteContext, onRunCommand }: CommandPaletteDialogProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  const commands = useMemo(() => buildPaletteCommands(paletteContext), [paletteContext])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return commands
    return commands.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.hint.toLowerCase().includes(q) ||
        c.category.includes(q) ||
        c.keywords?.some((k) => k.toLowerCase().includes(q)),
    )
  }, [commands, query])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const activeIndex = Math.min(selectedIndex, Math.max(0, filtered.length - 1))

  const runSelected = () => {
    const command = filtered[activeIndex]
    if (!command) return
    onRunCommand(command)
    onClose()
  }

  let lastCategory: CommandCategory | null = null

  return (
    <div className="cmdPaletteBackdrop" onClick={onClose}>
      <div
        className="cmdPalette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          className="cmdPaletteInput"
          autoFocus
          placeholder="Search commands… (↑↓ select, Enter run, Esc close)"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelectedIndex(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setSelectedIndex((i) => Math.min(i + 1, Math.max(0, filtered.length - 1)))
              return
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              setSelectedIndex((i) => Math.max(i - 1, 0))
              return
            }
            if (e.key === 'Enter') {
              e.preventDefault()
              runSelected()
            }
          }}
        />
        <ul className="cmdPaletteList" role="listbox">
          {filtered.map((command, idx) => {
            const showHeader = command.category !== lastCategory
            lastCategory = command.category
            return (
              <li key={command.id} role="presentation">
                {showHeader ? <div className="cmdPaletteCategory">{CATEGORY_LABELS[command.category]}</div> : null}
                <button
                  type="button"
                  role="option"
                  aria-selected={idx === activeIndex}
                  className={idx === activeIndex ? 'cmdPaletteItem cmdPaletteItemSelected' : 'cmdPaletteItem'}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => {
                    onRunCommand(command)
                    onClose()
                  }}
                >
                  <span className="cmdPaletteLabel">{command.label}</span>
                  <span className="cmdPaletteHint">{command.hint}</span>
                </button>
              </li>
            )
          })}
          {filtered.length === 0 ? <li className="cmdPaletteEmpty">No matches.</li> : null}
        </ul>
      </div>
    </div>
  )
}

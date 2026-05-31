import { useEffect, useMemo, useState } from 'react'

import { SMART_ACTIONS, type SmartAction } from '../lib/smartActions'



type CommandPaletteProps = {

  open: boolean

  onClose: () => void

  onRunAction: (action: SmartAction) => void

}



export function CommandPalette({ open, onClose, onRunAction }: CommandPaletteProps) {
  if (!open) return null

  return <CommandPaletteDialog onClose={onClose} onRunAction={onRunAction} />
}

type CommandPaletteDialogProps = Omit<CommandPaletteProps, 'open'>

function CommandPaletteDialog({ onClose, onRunAction }: CommandPaletteDialogProps) {

  const [query, setQuery] = useState('')

  const [selectedIndex, setSelectedIndex] = useState(0)



  const filtered = useMemo(() => {

    const q = query.trim().toLowerCase()

    if (!q) return SMART_ACTIONS

    return SMART_ACTIONS.filter(

      (a) =>

        a.label.toLowerCase().includes(q) ||

        a.hint.toLowerCase().includes(q) ||

        a.category.includes(q),

    )

  }, [query])



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
    const action = filtered[activeIndex]

    if (!action) return

    onRunAction(action)

    onClose()

  }



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

          placeholder="Search actions… (↑↓ select, Enter run, Esc close)"

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

          {filtered.map((action, idx) => (

            <li key={action.id} role="presentation">

              <button

                type="button"

                role="option"

                aria-selected={idx === activeIndex}

                className={

                  idx === activeIndex ? 'cmdPaletteItem cmdPaletteItemSelected' : 'cmdPaletteItem'

                }

                onMouseEnter={() => setSelectedIndex(idx)}

                onClick={() => {

                  onRunAction(action)

                  onClose()

                }}

              >

                <span className="cmdPaletteLabel">{action.label}</span>

                <span className="cmdPaletteHint">{action.hint}</span>

              </button>

            </li>

          ))}

          {filtered.length === 0 ? <li className="cmdPaletteEmpty">No matches.</li> : null}

        </ul>

      </div>

    </div>

  )

}


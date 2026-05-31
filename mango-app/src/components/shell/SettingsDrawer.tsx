import { useCallback, useEffect, useState } from 'react'
import type { MangoSettings } from '../../types/ui'
import { SettingsPanel } from '../SettingsPanel'
import { ConfirmDialog } from '../ConfirmDialog'

type SettingsDrawerProps = {
  open: boolean
  running: boolean
  settings: MangoSettings
  savedSettings: MangoSettings
  onChange: (next: MangoSettings) => void
  onClose: () => void
  onSave: () => void
  onSaveAndRestart: () => void
  onOpenLogs: () => void
  onCopyDiagnostics: () => void
  onExportJson: () => void
  onExportCsv: () => void
}

export function SettingsDrawer({
  open,
  running,
  settings,
  savedSettings,
  onChange,
  onClose,
  onSave,
  onSaveAndRestart,
  onOpenLogs,
  onCopyDiagnostics,
  onExportJson,
  onExportCsv,
}: SettingsDrawerProps) {
  const dirty = JSON.stringify(settings) !== JSON.stringify(savedSettings)
  const [confirmDiscard, setConfirmDiscard] = useState(false)

  const requestClose = useCallback(() => {
    if (dirty) {
      setConfirmDiscard(true)
      return
    }
    onClose()
  }, [dirty, onClose])

  useEffect(() => {
    if (!open) setConfirmDiscard(false)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !confirmDiscard) {
        e.preventDefault()
        requestClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, requestClose, confirmDiscard])

  if (!open) return null

  return (
    <>
      <div className="settingsDrawerBackdrop" onClick={requestClose} role="presentation">
        <aside
          className="settingsDrawer glass-panel"
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
          onClick={(e) => e.stopPropagation()}
        >
          <header className="settingsDrawerHead">
            <div>
              <h2>Settings</h2>
              <p className="panelSub">
                {running ? 'Save applies on next restart unless you use Save & restart.' : 'Save to persist preferences.'}
              </p>
            </div>
            <button type="button" className="ghostBtn" onClick={requestClose} aria-label="Close settings">
              ✕
            </button>
          </header>

          <div className="settingsDrawerBody">
            <SettingsPanel
              settings={settings}
              savedSettings={savedSettings}
              onChange={onChange}
              onSave={onSave}
              onOpenLogs={onOpenLogs}
              onCopyDiagnostics={onCopyDiagnostics}
              onExportJson={onExportJson}
              onExportCsv={onExportCsv}
              embedded
            />
          </div>

          <footer className="settingsDrawerFoot">
            {dirty ? <span className="unsavedBadge">Unsaved changes</span> : <span className="settingsSavedHint">Up to date</span>}
            <div className="settingsDrawerActions">
              <button type="button" className="ghostBtn" onClick={requestClose}>
                Cancel
              </button>
              <button type="button" className="btnSecondary" onClick={onSave} disabled={!dirty}>
                Save
              </button>
              {running ? (
                <button type="button" className="glassBtnPrimary" onClick={onSaveAndRestart} disabled={!dirty}>
                  Save & restart
                </button>
              ) : (
                <button type="button" className="glassBtnPrimary" onClick={onSave} disabled={!dirty}>
                  Save
                </button>
              )}
            </div>
          </footer>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmDiscard}
        title="Discard changes?"
        message="You have unsaved settings. Discard changes and close?"
        confirmLabel="Discard"
        cancelLabel="Keep editing"
        onConfirm={() => {
          setConfirmDiscard(false)
          onClose()
        }}
        onCancel={() => setConfirmDiscard(false)}
      />
    </>
  )
}

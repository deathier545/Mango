import type { MangoSettings } from '../types/ui'

type SettingsPanelProps = {
  settings: MangoSettings
  savedSettings: MangoSettings
  onChange: (next: MangoSettings) => void
  onSave: () => void
  onOpenLogs: () => void
  onCopyDiagnostics: () => void
  onExportJson: () => void
  onExportCsv: () => void
}

type SpeechPresetId = 'clear' | 'natural' | 'fast'

const SPEECH_PRESETS: Record<
  SpeechPresetId,
  Pick<MangoSettings, 'edgeRate' | 'edgePitch' | 'edgeVolume' | 'interruptProfile'>
> = {
  clear: {
    edgeRate: '-14%',
    edgePitch: '-2Hz',
    edgeVolume: '+8%',
    interruptProfile: 'strict',
  },
  natural: {
    edgeRate: '-8%',
    edgePitch: '+0Hz',
    edgeVolume: '+0%',
    interruptProfile: 'normal',
  },
  fast: {
    edgeRate: '+4%',
    edgePitch: '+1Hz',
    edgeVolume: '+2%',
    interruptProfile: 'fast',
  },
}

function settingsEqual(a: MangoSettings, b: MangoSettings): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

function detectSpeechPreset(settings: MangoSettings): SpeechPresetId | 'custom' {
  const entry = (Object.entries(SPEECH_PRESETS) as Array<[SpeechPresetId, (typeof SPEECH_PRESETS)[SpeechPresetId]]>).find(
    ([, preset]) =>
      settings.edgeRate === preset.edgeRate &&
      settings.edgePitch === preset.edgePitch &&
      settings.edgeVolume === preset.edgeVolume &&
      settings.interruptProfile === preset.interruptProfile,
  )
  return entry ? entry[0] : 'custom'
}

export function SettingsPanel({
  settings,
  savedSettings,
  onChange,
  onSave,
  onOpenLogs,
  onCopyDiagnostics,
  onExportJson,
  onExportCsv,
}: SettingsPanelProps) {
  const dirty = !settingsEqual(settings, savedSettings)
  const speechPreset = detectSpeechPreset(settings)

  return (
    <section className="contentGrid settingsGrid">
      <section className="panel">
        <header className="panelHead">
          <div>
            <h2>Settings</h2>
            <p className="panelSub">Voice and model preferences. Save applies on next restart if Mango is running.</p>
          </div>
          <div className="settingsHeadActions">
            {dirty ? <span className="unsavedBadge">Unsaved changes</span> : null}
            <button type="button" className="btnPrimary" onClick={onSave} disabled={!dirty}>
              Save settings
            </button>
          </div>
        </header>
        <div className="settings">
          <h3>Core</h3>
          <label title="Listen for “hey mango” when Mango is running">
            <input
              type="checkbox"
              checked={settings.wakeEnabled}
              onChange={(e) => onChange({ ...settings, wakeEnabled: e.target.checked })}
            />
            Wake word enabled
          </label>
          <label title="Require stricter validation before running tools">
            <input
              type="checkbox"
              checked={settings.strictTools}
              onChange={(e) => onChange({ ...settings, strictTools: e.target.checked })}
            />
            Strict tool validation
          </label>
          <label title="Ask before running PowerShell commands">
            <input
              type="checkbox"
              checked={settings.powershellConfirmation}
              onChange={(e) => onChange({ ...settings, powershellConfirmation: e.target.checked })}
            />
            PowerShell confirmation
          </label>
          <h3>Model and speech</h3>
          <label>
            Groq model
            <span className="fieldHelp">Model ID passed to the Groq API for chat.</span>
            <input
              className="modelInput"
              value={settings.groqModel}
              onChange={(e) => onChange({ ...settings, groqModel: e.target.value })}
            />
          </label>
          <label>
            Speech clarity preset
            <span className="fieldHelp">Quick tuning for clarity and interruption behavior.</span>
            <select
              className="modelInput"
              value={speechPreset === 'custom' ? '' : speechPreset}
              onChange={(e) => {
                const next = e.target.value as SpeechPresetId
                onChange({ ...settings, ...SPEECH_PRESETS[next] })
              }}
            >
              <option value="" disabled>
                custom (edited)
              </option>
              <option value="clear">clear (slower, louder)</option>
              <option value="natural">natural (balanced)</option>
              <option value="fast">fast (quicker replies)</option>
            </select>
            {speechPreset === 'custom' ? (
              <span className="fieldHelp">Custom values active. Pick a preset to re-apply defaults.</span>
            ) : null}
          </label>
          <label>
            Edge voice
            <span className="fieldHelp">Voice ID for Edge TTS (speech output voice).</span>
            <input
              className="modelInput"
              value={settings.edgeVoice}
              onChange={(e) => onChange({ ...settings, edgeVoice: e.target.value })}
            />
          </label>
          <label>
            Speech rate
            <span className="fieldHelp">Use percent format like -8% (slower) or +5% (faster).</span>
            <input
              className="modelInput"
              value={settings.edgeRate}
              onChange={(e) => onChange({ ...settings, edgeRate: e.target.value })}
            />
          </label>
          <label>
            Speech pitch
            <span className="fieldHelp">Use Hz format like +0Hz, -20Hz, or +10Hz.</span>
            <input
              className="modelInput"
              value={settings.edgePitch}
              onChange={(e) => onChange({ ...settings, edgePitch: e.target.value })}
            />
          </label>
          <label>
            Speech volume
            <span className="fieldHelp">Use percent format like +0%, +5%, or -5%.</span>
            <input
              className="modelInput"
              value={settings.edgeVolume}
              onChange={(e) => onChange({ ...settings, edgeVolume: e.target.value })}
            />
          </label>
          <label>
            Interrupt profile
            <span className="fieldHelp">Fast interrupts quickly, strict avoids accidental cut-ins.</span>
            <select
              className="modelInput"
              value={settings.interruptProfile}
              onChange={(e) =>
                onChange({
                  ...settings,
                  interruptProfile: e.target.value as MangoSettings['interruptProfile'],
                })
              }
            >
              <option value="strict">strict</option>
              <option value="normal">normal</option>
              <option value="fast">fast</option>
            </select>
          </label>
          <h3>Cost estimate</h3>
          <label>
            Prompt token rate ($ / 1k)
            <span className="fieldHelp">Used for session cost estimate on Metrics.</span>
            <input
              className="modelInput"
              type="number"
              step="0.0001"
              value={settings.promptTokenRatePer1k}
              onChange={(e) =>
                onChange({ ...settings, promptTokenRatePer1k: Number(e.target.value || 0) })
              }
            />
          </label>
          <label>
            Completion token rate ($ / 1k)
            <span className="fieldHelp">Used for session cost estimate on Metrics.</span>
            <input
              className="modelInput"
              type="number"
              step="0.0001"
              value={settings.completionTokenRatePer1k}
              onChange={(e) =>
                onChange({ ...settings, completionTokenRatePer1k: Number(e.target.value || 0) })
              }
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <h2>Advanced diagnostics</h2>
        <p className="panelSub">Export usage, open log files, or copy a snapshot for debugging.</p>
        <div className="diagButtons">
          <button type="button" className="btnSecondary" onClick={onOpenLogs}>
            Open logs folder
          </button>
          <button type="button" className="btnSecondary" onClick={onCopyDiagnostics}>
            Copy diagnostics
          </button>
          <button type="button" className="btnSecondary" onClick={onExportJson}>
            Export usage JSON
          </button>
          <button type="button" className="btnSecondary" onClick={onExportCsv}>
            Export usage CSV
          </button>
        </div>
      </section>
    </section>
  )
}

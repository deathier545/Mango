import type { AppView } from '../types/ui'

const TABS: { id: AppView; label: string; hint: string; shortcut: string }[] = [
  { id: 'mango', label: 'Mango', hint: 'Voice orb & map', shortcut: 'Ctrl+1' },
  { id: 'chat', label: 'Chat', hint: 'Type messages to Mango', shortcut: 'Ctrl+2' },
  {
    id: 'conversation',
    label: 'Voice log',
    hint: 'Wake/PTT transcript & system logs',
    shortcut: 'Ctrl+3',
  },
  { id: 'metrics', label: 'Metrics', hint: 'Latency, tokens, tools', shortcut: 'Ctrl+4' },
  { id: 'smart', label: 'Smart', hint: 'Memory, routines, timeline', shortcut: 'Ctrl+5' },
  { id: 'settings', label: 'Settings', hint: 'Preferences & diagnostics', shortcut: 'Ctrl+6' },
]

type TabNavProps = {
  activeView: AppView
  onView: (view: AppView) => void
  onMangoTab: () => void
}

export function TabNav({ activeView, onView, onMangoTab }: TabNavProps) {
  return (
    <nav className="bottomTabs" aria-label="Main navigation">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={activeView === tab.id ? 'tabBtn active' : 'tabBtn'}
          title={`${tab.hint} (${tab.shortcut})`}
          aria-current={activeView === tab.id ? 'page' : undefined}
          aria-label={tab.label}
          aria-keyshortcuts={tab.shortcut.replace('Ctrl+', 'Control+')}
          onClick={() => {
            if (tab.id === 'mango') onMangoTab()
            else onView(tab.id)
          }}
        >
          <span className="tabLabel">{tab.label}</span>
          <span className="tabHint">{tab.hint}</span>
        </button>
      ))}
    </nav>
  )
}

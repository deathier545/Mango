import type { AppZone } from '../types/ui'
import type { SmartAction } from './smartActions'
import { SMART_ACTIONS } from './smartActions'

export type CommandCategory = 'action' | 'prompt' | 'nav' | 'smart' | 'diagnostics'

export type PaletteCommand = {
  id: string
  label: string
  hint: string
  category: CommandCategory
  keywords?: string[]
  smartAction?: SmartAction
}

export type PaletteContext = {
  setZone: (zone: AppZone) => void
  openSettings: () => void
  startMango: () => void
  stopMango: () => void
  restartMango: () => void
  clearTyped: () => void
  clearAll: () => void
  openLogs: () => void
  copyDiagnostics: () => void
  toggleContextRail: () => void
  running: boolean
}

export function buildPaletteCommands(ctx: PaletteContext): PaletteCommand[] {
  const prompts: PaletteCommand[] = SMART_ACTIONS.filter((a) => a.prompt).map((a) => ({
    id: `smart-${a.id}`,
    label: a.label,
    hint: a.hint,
    category: a.category === 'nav' || a.category === 'memory' ? 'smart' : 'prompt',
    keywords: [a.category, a.prompt],
    smartAction: a,
  }))

  const nav: PaletteCommand[] = [
    { id: 'nav-command', label: 'Go to Command', hint: 'Conversation', category: 'nav', keywords: ['chat', 'home'] },
    { id: 'nav-smart', label: 'Go to Smart', hint: 'Memory & badges', category: 'nav', keywords: ['memory'] },
    { id: 'nav-diagnostics', label: 'Go to Diagnostics', hint: 'Metrics & logs', category: 'nav', keywords: ['metrics'] },
    { id: 'nav-settings', label: 'Open Settings', hint: 'Preferences', category: 'nav', keywords: ['config'] },
  ]

  const actions: PaletteCommand[] = [
    ...(ctx.running
      ? []
      : [
          {
            id: 'start-mango',
            label: 'Start Mango',
            hint: 'Voice + tools',
            category: 'action' as const,
            keywords: ['run', 'launch'],
          },
        ]),
    ...(ctx.running
      ? [
          {
            id: 'stop-mango',
            label: 'Stop Mango',
            hint: 'End session',
            category: 'action' as const,
            keywords: ['quit'],
          },
        ]
      : []),
    {
      id: 'restart-mango',
      label: 'Restart Mango',
      hint: 'Apply settings',
      category: 'action',
      keywords: ['reload'],
    },
    {
      id: 'toggle-context',
      label: 'Toggle context panel',
      hint: 'Map & tools',
      category: 'action',
      keywords: ['map', 'rail'],
    },
    {
      id: 'clear-typed',
      label: 'Clear typed messages',
      hint: 'Chat only',
      category: 'action',
    },
    {
      id: 'clear-all',
      label: 'Clear all conversation',
      hint: 'Voice + typed',
      category: 'action',
    },
  ]

  const diagnostics: PaletteCommand[] = [
    { id: 'open-logs', label: 'Open logs folder', hint: 'Diagnostics', category: 'diagnostics' },
    { id: 'copy-diagnostics', label: 'Copy diagnostics', hint: 'Clipboard', category: 'diagnostics' },
  ]

  const smartNav: PaletteCommand[] = SMART_ACTIONS.filter((a) => !a.prompt).map((a) => ({
    id: `smart-${a.id}`,
    label: a.label,
    hint: a.hint,
    category: 'smart' as const,
    smartAction: a,
  }))

  return [...actions, ...nav, ...diagnostics, ...smartNav, ...prompts]
}

export function runPaletteCommand(id: string, ctx: PaletteContext, onSmartAction: (a: SmartAction) => void): boolean {
  const cmd = buildPaletteCommands(ctx).find((c) => c.id === id)
  if (!cmd) return false

  if (cmd.smartAction) {
    onSmartAction(cmd.smartAction)
    return true
  }

  switch (id) {
    case 'nav-command':
      ctx.setZone('command')
      return true
    case 'nav-smart':
      ctx.setZone('intelligence')
      return true
    case 'nav-diagnostics':
      ctx.setZone('diagnostics')
      return true
    case 'nav-settings':
      ctx.openSettings()
      return true
    case 'start-mango':
      if (!ctx.running) ctx.startMango()
      return true
    case 'stop-mango':
      if (ctx.running) ctx.stopMango()
      return true
    case 'restart-mango':
      ctx.restartMango()
      return true
    case 'toggle-context':
      ctx.toggleContextRail()
      return true
    case 'clear-typed':
      ctx.clearTyped()
      return true
    case 'clear-all':
      ctx.clearAll()
      return true
    case 'open-logs':
      ctx.openLogs()
      return true
    case 'copy-diagnostics':
      ctx.copyDiagnostics()
      return true
    default:
      return false
  }
}

export const CATEGORY_LABELS: Record<CommandCategory, string> = {
  action: 'Actions',
  nav: 'Navigate',
  prompt: 'Prompts',
  smart: 'Smart',
  diagnostics: 'Diagnostics',
}

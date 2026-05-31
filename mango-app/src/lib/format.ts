import type { OrbState } from '../types/ui'

const TOOL_CALL_ONLY_RE = /^\s*<function>([^<]+)<\/function>\s*(\{[\s\S]*\})?\s*$/i

export function cleanUiText(value: string): string {
  const raw = String(value || '').replace(/\uFFFD/g, '').trim()
  if (!raw) return ''

  const toolCallOnly = raw.match(TOOL_CALL_ONLY_RE)
  if (toolCallOnly) {
    const toolName = toolCallOnly[1].trim()
    const args = (toolCallOnly[2] || '').trim()
    return args ? `Running tool: ${toolName} ${args}` : `Running tool: ${toolName}`
  }

  return raw
}

const STATE_LABELS: Record<OrbState, string> = {
  idle: 'Ready',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  awaiting: 'Confirm?',
  stopped: 'Stopped',
  error: 'Error',
}

export function assistantStateLabel(state: string, running: boolean): string {
  if (state === 'error') return STATE_LABELS.error
  if (state in STATE_LABELS) return STATE_LABELS[state as OrbState]
  return running ? STATE_LABELS.listening : STATE_LABELS.idle
}

export function orbCaption(state: OrbState, running: boolean): string {
  if (!running) return 'Voice offline — press Start to enable wake word and push-to-talk.'
  switch (state) {
    case 'listening':
      return 'Listening — say “hey mango” or hold Alt+W while you speak.'
    case 'thinking':
      return 'Working on your request…'
    case 'speaking':
      return 'Speaking…'
    case 'awaiting':
      return 'Waiting for your confirmation.'
    case 'stopped':
      return 'Mango voice is stopped.'
    case 'error':
      return 'Something went wrong — check Voice log or Metrics.'
    default:
      return 'Online — say “hey mango” or hold Alt+W.'
  }
}

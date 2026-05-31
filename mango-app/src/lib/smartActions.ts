export type SmartAction = {
  id: string
  label: string
  hint: string
  prompt: string
  category: 'routine' | 'memory' | 'clipboard' | 'brief' | 'discord' | 'nav'
}

export const SMART_ACTIONS: SmartAction[] = [
  {
    id: 'brief',
    label: 'Daily briefing',
    hint: 'Memory, reminders, system',
    prompt: 'Give me my daily briefing.',
    category: 'brief',
  },
  {
    id: 'join_play',
    label: 'Join Discord + play',
    hint: 'Routine',
    prompt: 'Run routine join_discord_play for Bad Romance.',
    category: 'routine',
  },
  {
    id: 'discord_hi_play',
    label: 'Join, greet, play at 50%',
    hint: 'Routine — one tool call',
    prompt:
      'Run routine discord_hi_and_play with the song Bad Romance and volume 50.',
    category: 'routine',
  },
  {
    id: 'night',
    label: 'Night mode',
    hint: 'Lower volume, stop Discord music',
    prompt: 'Run routine night_mode.',
    category: 'routine',
  },
  {
    id: 'focus',
    label: 'Focus mode',
    hint: 'Moderate volume cue',
    prompt: 'Run routine focus_mode.',
    category: 'routine',
  },
  {
    id: 'clip_sum',
    label: 'Summarize clipboard',
    hint: 'Clipboard AI',
    prompt: 'Summarize my clipboard.',
    category: 'clipboard',
  },
  {
    id: 'clip_todos',
    label: 'Todos from clipboard',
    hint: 'Extract action items',
    prompt: 'Extract todos from my clipboard.',
    category: 'clipboard',
  },
  {
    id: 'remember',
    label: 'Remember this',
    hint: 'Opens Smart tab',
    prompt: '',
    category: 'memory',
  },
  {
    id: 'open_smart',
    label: 'Open Smart tab',
    hint: 'Memory, timeline, routines',
    prompt: '',
    category: 'nav',
  },
]

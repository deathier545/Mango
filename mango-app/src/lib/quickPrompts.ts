export type QuickPrompt = {
  label: string
  prompt: string
}

/** Shared quick prompts for Chat and Mango HUD (sentence case labels). */
export const CHAT_QUICK_PROMPTS: QuickPrompt[] = [
  { label: 'System check', prompt: 'Give me a quick system check summary.' },
  { label: 'Open DeKalb map', prompt: 'Show me DeKalb, Illinois on the map.' },
  { label: 'What next?', prompt: 'What should I focus on next today?' },
]

export const HUD_QUICK_PROMPTS: QuickPrompt[] = [
  { label: 'Spotify → Discord', prompt: 'Play something on Spotify for the Discord call.' },
  ...CHAT_QUICK_PROMPTS,
]

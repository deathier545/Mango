import { useEffect, useState } from 'react'
import type { DiscordBridgeStatus } from '../types/ui'

const DEFAULT: DiscordBridgeStatus = {
  ok: false,
  musicOn: false,
  ownerVoice: null,
  reachable: false,
}

function parseBridgePayload(data: {
  ok?: boolean
  owner_voice?: string | null
  lines?: string[]
}): DiscordBridgeStatus {
  const lines = Array.isArray(data.lines) ? data.lines.join(' ') : ''
  return {
    ok: Boolean(data.ok),
    ownerVoice: data.owner_voice ?? null,
    musicOn: /music stream:\s*on/i.test(lines),
    reachable: true,
  }
}

async function pollViaRenderer(): Promise<DiscordBridgeStatus> {
  const r = await fetch('http://127.0.0.1:37564/v1/voice/status', {
    signal: AbortSignal.timeout(4000),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return parseBridgePayload((await r.json()) as { ok?: boolean; owner_voice?: string | null; lines?: string[] })
}

export function useDiscordBridgeStatus(enabled: boolean, intervalMs = 8_000) {
  const [status, setStatus] = useState<DiscordBridgeStatus>(DEFAULT)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    const poll = async () => {
      try {
        if (window.mango?.getDiscordBridgeStatus) {
          const data = await window.mango.getDiscordBridgeStatus()
          if (!cancelled) {
            setStatus(
              data.reachable
                ? {
                    ok: data.ok,
                    musicOn: data.musicOn,
                    ownerVoice: data.ownerVoice,
                    reachable: true,
                  }
                : DEFAULT,
            )
          }
          return
        }
        const parsed = await pollViaRenderer()
        if (!cancelled) setStatus(parsed)
      } catch {
        if (!cancelled) setStatus(DEFAULT)
      }
    }

    void poll()
    const id = window.setInterval(() => void poll(), intervalMs)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [enabled, intervalMs])

  return enabled ? status : DEFAULT
}

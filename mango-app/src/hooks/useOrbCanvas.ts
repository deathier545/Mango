import { useEffect, type RefObject } from 'react'
import type { OrbState } from '../types/ui'
import { ORB_TARGETS } from '../orb/orbConfig'

export function useOrbCanvas(
  enabled: boolean,
  orbState: OrbState,
  orbWrapRef: RefObject<HTMLDivElement | null>,
  orbCanvasRef: RefObject<HTMLCanvasElement | null>,
  audioLevelRef: RefObject<number>,
  orbStateRef: RefObject<OrbState>,
) {
  useEffect(() => {
    orbStateRef.current = orbState
  }, [orbState, orbStateRef])

  useEffect(() => {
    if (!enabled) return
    const canvas = orbCanvasRef.current
    const host = orbWrapRef.current
    if (!canvas || !host) return
    window.requestAnimationFrame(() => {
      const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2))
      const w = host.clientWidth
      const h = host.clientHeight
      if (!w || !h) return
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
    })
  }, [enabled, orbCanvasRef, orbWrapRef])

  useEffect(() => {
    if (!enabled) return
    const canvas = orbCanvasRef.current
    const host = orbWrapRef.current
    if (!canvas || !host) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const count = 880
    const goldenAngle = Math.PI * (3 - Math.sqrt(5))
    const linkSteps = [1, 13, 29]
    const unitPoints = Array.from({ length: count }, (_, i) => {
      const y = 1 - (2 * (i + 0.5)) / count
      const ring = Math.sqrt(Math.max(0, 1 - y * y))
      const theta = goldenAngle * i
      return {
        x: Math.cos(theta) * ring,
        y,
        z: Math.sin(theta) * ring,
        phaseA: (i % 97) * 0.071,
      }
    })

    let raf = 0
    let lastW = 0
    let lastH = 0
    let dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2))
    const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t
    const smooth = (current: number, target: number, dt: number, speed: number) => {
      const amount = 1 - Math.exp(-speed * dt)
      return lerp(current, target, amount)
    }
    const smoothRgb = (
      current: [number, number, number],
      target: [number, number, number],
      dt: number,
      speed: number,
    ): [number, number, number] => [
      smooth(current[0], target[0], dt, speed),
      smooth(current[1], target[1], dt, speed),
      smooth(current[2], target[2], dt, speed),
    ]
    let lastFrameMs = performance.now()
    let rotationY = 0
    const visual = {
      rgb: [83, 216, 255] as [number, number, number],
      rotSpeed: 0.18,
      breath: 0.006,
      dotBoost: 1.15,
    }

    const draw = (timeMs: number) => {
      if (!enabled) return
      const w = host.clientWidth
      const h = host.clientHeight
      if (!w || !h) {
        raf = requestAnimationFrame(draw)
        return
      }

      if (w !== lastW || h !== lastH) {
        lastW = w
        lastH = h
        dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2))
        canvas.width = Math.floor(w * dpr)
        canvas.height = Math.floor(h * dpr)
        canvas.style.width = `${w}px`
        canvas.style.height = `${h}px`
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const t = timeMs * 0.001
      const cx = w * 0.5
      const cy = h * 0.5
      const baseRadius = Math.min(w, h) * 0.42
      const nowMs = timeMs
      const dt = clamp01((nowMs - lastFrameMs) / 1000)
      lastFrameMs = nowMs
      const stateNow = orbStateRef.current ?? 'idle'
      const target = ORB_TARGETS[stateNow] ?? ORB_TARGETS.idle

      const realLevel = clamp01(audioLevelRef.current ?? 0)
      // Pulse from real TTS loudness whenever audio is playing (not only ai_state=speaking).
      const audible = realLevel > 0.025
      const speakingPulse = audible
        ? Math.max(realLevel, 0.12 + 0.1 * Math.sin(t * 7.7))
        : stateNow === 'speaking'
          ? Math.max(realLevel, 0.18 + 0.18 * Math.sin(t * 7.7))
          : 0
      const motionSpeaking = audible || stateNow === 'speaking'
      audioLevelRef.current = (audioLevelRef.current ?? 0) * 0.86
      const motionTarget = motionSpeaking ? ORB_TARGETS.speaking : target
      visual.rgb = smoothRgb(visual.rgb, motionTarget.rgb, dt, audible ? 6.5 : 4.2)
      visual.rotSpeed = smooth(visual.rotSpeed, motionTarget.rotSpeed, dt, audible ? 5.5 : 3.2)
      visual.breath = smooth(visual.breath, motionTarget.breath, dt, audible ? 6.0 : 4.2)
      visual.dotBoost = smooth(visual.dotBoost, motionTarget.dotBoost, dt, audible ? 6.0 : 4.2)
      const stateRgb = visual.rgb.map((v) => Math.round(v)) as [number, number, number]
      rotationY += visual.rotSpeed * dt
      const rotY = rotationY
      const rotX = 0.16 * Math.sin(t * 0.55)
      const breathWave = Math.sin(t * 1.8)
      const breath = 0.77 + visual.breath * (motionSpeaking ? speakingPulse : breathWave)
      const jitter = motionSpeaking ? 0.01 * speakingPulse : 0
      const cosY = Math.cos(rotY)
      const sinY = Math.sin(rotY)
      const cosX = Math.cos(rotX)
      const sinX = Math.sin(rotX)

      const projected = unitPoints.map((p) => {
        let x = cosY * p.x + sinY * p.z
        let z = -sinY * p.x + cosY * p.z
        let y = p.y
        const y2 = cosX * y - sinX * z
        z = sinX * y + cosX * z
        y = y2
        if (jitter > 0) {
          const j = jitter * Math.sin(t * 11.5 + p.phaseA)
          x += j
          y += j * 0.8
        }
        const depth = (z + 1) / 2
        const proj = 0.6 + depth * 0.4
        return {
          x: cx + x * baseRadius * breath * proj,
          y: cy + y * baseRadius * breath * proj * 0.95,
          depth,
        }
      })

      const glow = ctx.createRadialGradient(cx, cy, baseRadius * 0.1, cx, cy, baseRadius * 1.05)
      const glowAlpha = motionSpeaking ? 0.13 : stateNow === 'error' ? 0.11 : 0.08
      glow.addColorStop(0, `rgba(${stateRgb[0]}, ${stateRgb[1]}, ${stateRgb[2]}, ${glowAlpha})`)
      glow.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(cx, cy, baseRadius * 1.06, 0, Math.PI * 2)
      ctx.fill()

      ctx.lineWidth = 0.7
      for (let i = 0; i < projected.length; i += 1) {
        const a = projected[i]
        for (const step of linkSteps) {
          const b = projected[(i + step) % projected.length]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > 26) continue
          const alpha = (1 - dist / 26) * (0.06 + ((a.depth + b.depth) * 0.5) * 0.22)
          ctx.strokeStyle = `rgba(${stateRgb[0]}, ${stateRgb[1]}, ${stateRgb[2]}, ${alpha.toFixed(3)})`
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
      }

      projected.sort((a, b) => a.depth - b.depth)
      for (const p of projected) {
        const alphaFloor = motionSpeaking ? 0.24 : stateNow === 'stopped' ? 0.14 : 0.16
        const alpha = alphaFloor + p.depth * (1 - alphaFloor)
        const r = 0.85 + p.depth * visual.dotBoost
        ctx.fillStyle = `rgba(${stateRgb[0]}, ${stateRgb[1]}, ${stateRgb[2]}, ${alpha.toFixed(3)})`
        ctx.beginPath()
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
        ctx.fill()
      }

      raf = requestAnimationFrame(draw)
    }

    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [enabled, orbCanvasRef, orbWrapRef, audioLevelRef, orbStateRef])
}

import { useEffect, useState } from 'react'

export function useAnimatedNumber(
  value: number | null | undefined,
  format: (n: number) => string = (n) => n.toFixed(2),
  durationMs = 420,
): string {
  const [display, setDisplay] = useState('—')

  useEffect(() => {
    if (value == null || !Number.isFinite(value)) {
      const frame = requestAnimationFrame(() => setDisplay('—'))
      return () => cancelAnimationFrame(frame)
    }
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReduced) {
      const frame = requestAnimationFrame(() => setDisplay(format(value)))
      return () => cancelAnimationFrame(frame)
    }
    const from = 0
    const to = value
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - (1 - t) ** 3
      setDisplay(format(from + (to - from) * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, format, durationMs])

  return display
}

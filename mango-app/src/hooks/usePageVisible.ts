import { useEffect, useState } from 'react'

/** True when the window tab is visible and the window has focus (for pausing animations). */
export function usePageVisible() {
  const [visible, setVisible] = useState(
    () => typeof document !== 'undefined' && document.visibilityState === 'visible',
  )

  useEffect(() => {
    const sync = () => {
      setVisible(document.visibilityState === 'visible' && document.hasFocus())
    }
    sync()
    document.addEventListener('visibilitychange', sync)
    window.addEventListener('focus', sync)
    window.addEventListener('blur', sync)
    return () => {
      document.removeEventListener('visibilitychange', sync)
      window.removeEventListener('focus', sync)
      window.removeEventListener('blur', sync)
    }
  }, [])

  return visible
}

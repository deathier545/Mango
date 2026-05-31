/** Must match `bridgeVersion` in electron/preload.cjs */
export const MANGO_BRIDGE_VERSION = 2

export function hasMangoBridge(): boolean {
  return typeof window !== 'undefined' && typeof window.mango === 'object' && window.mango !== null
}

export function hasDuoBridge(): boolean {
  return (
    hasMangoBridge() &&
    window.mango.bridgeVersion === MANGO_BRIDGE_VERSION &&
    typeof window.mango.runDuo === 'function' &&
    typeof window.mango.stopDuo === 'function'
  )
}

export function mangoBridgeVersion(): number | null {
  if (!hasMangoBridge()) return null
  const version = window.mango.bridgeVersion
  return typeof version === 'number' ? version : null
}

export function duoUnavailableMessage(): string {
  if (!hasMangoBridge()) {
    return 'Open Mango Console from Electron (npm run dev or npm start), not a browser tab.'
  }
  if (window.mango.bridgeVersion !== MANGO_BRIDGE_VERSION) {
    return 'Desktop bridge is outdated. Fully quit Mango Console and start it again (npm run dev).'
  }
  if (typeof window.mango.runDuo !== 'function' || typeof window.mango.stopDuo !== 'function') {
    return 'Duo requires an updated desktop bridge. Fully quit Mango Console and run npm run dev again.'
  }
  return 'Duo needs the Mango Console desktop app. Quit any browser tab preview and use the Electron window.'
}

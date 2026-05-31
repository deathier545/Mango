export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }

/** Unwrap `{ ok, data }` from Electron IPC; pass through legacy bare values. */
export function unwrapIpcData<T>(result: T | IpcResult<T>): T {
  if (result && typeof result === 'object' && 'ok' in result && 'data' in result) {
    const wrapped = result as IpcResult<T>
    if (!wrapped.ok) {
      throw new Error(wrapped.error || 'IPC call failed')
    }
    return wrapped.data as T
  }
  return result as T
}

/** Unwrap IPC result that may already use `{ ok, error }` without a data field. */
export function unwrapIpcOk(result: { ok: boolean; error?: string }): void {
  if (result && typeof result === 'object' && 'ok' in result && !result.ok) {
    throw new Error(result.error || 'IPC call failed')
  }
}

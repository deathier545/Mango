import { useToast } from '../context/ToastContext'

export function ToastStack() {
  const { toasts, dismissToast } = useToast()
  if (toasts.length === 0) return null

  return (
    <div className="toastStack" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`}>
          <span>{t.message}</span>
          <button type="button" className="toastDismiss" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

import { useState } from 'react'
import { useToast } from '../context/ToastContext'

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const { pushToast } = useToast()
  const [copied, setCopied] = useState(false)

  return (
    <button
      type="button"
      className="copyBtn"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          pushToast('Copied to clipboard.', 'success', 2500)
          window.setTimeout(() => setCopied(false), 2000)
        })
      }}
      aria-label={`${label} message`}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}

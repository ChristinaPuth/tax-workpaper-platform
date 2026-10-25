// Sensitive values arrive masked (•••-••-2287). Staff with clearance can show one value, page or person; the
// server logs every unmasked view. Staff without clearance are told why they cannot.
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api'
import { useSession } from '../session-context'

export const isMasked = (s: unknown) => typeof s === 'string' && s.includes('•')

export function useReveal(target: string) {
  // what was shown belongs to its target: another page or value starts masked again
  const [shown, setShown] = useState<{ target: string; content: Record<string, unknown> } | null>(null)
  const m = useMutation({
    mutationFn: () => api<{ target: string; content: Record<string, unknown> }>('/sensitive/reveal', { method: 'POST', body: JSON.stringify({ target }) }),
    onSuccess: (r) => setShown({ target: r.target, content: r.content }),
  })
  const content = shown?.target === target ? shown.content : null
  return { content, reveal: () => m.mutate(), pending: m.isPending, error: m.error as Error | null }
}

export function RevealButton({ r, what = 'value' }: { r: ReturnType<typeof useReveal>; what?: string }) {
  const { person } = useSession()
  if (!person || person.role === 'client') return null
  if (!person.sensitive_data_clearance) {
    return <span className="text-[11px] text-amber-800" title={person.note ?? ''}>masked · no sensitive-data clearance</span>
  }
  if (r.content) return <span className="text-[11px] text-slate-500">shown · this view is logged</span>
  return (
    <button className="text-[11px] text-indigo-700 hover:underline" disabled={r.pending} onClick={r.reveal}
      aria-label={`Show ${what} (logged)`} title="Shows the unmasked text; the firm logs who viewed what and when">
      Show {what} (logged)
    </button>
  )
}

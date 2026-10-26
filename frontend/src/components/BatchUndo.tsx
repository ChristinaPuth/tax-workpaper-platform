// After a bulk action (several decisions or sign-offs at once), one place to take it all back.
import { useLastBatch, useUndoBatch } from '../queries'
import { useQueryClient } from '@tanstack/react-query'
import { useSession } from '../session-context'

const WHAT: Record<string, string> = { judgment: 'decision', signoff: 'sign-off', note: 'note', adjust: 'change', verify: 'verification' }

export function BatchUndo() {
  const { data: batch } = useLastBatch()
  const undo = useUndoBatch()
  const qc = useQueryClient()
  const { actor } = useSession()
  if (!batch) return null
  const n = batch.events.length
  const kinds = [...new Set(batch.events.map((e) => e.type))]
  const what = kinds.length === 1 ? `${WHAT[kinds[0]] ?? kinds[0]}s` : 'actions'
  return (
    <div role="status" className="fixed bottom-4 left-4 z-40 flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13px] shadow-lg">
      <span className="text-slate-700">Recorded {n} {what} together.</span>
      <button className="btn" disabled={undo.isPending} onClick={() => undo.mutate(batch.batch_id)}>
        {undo.isPending ? 'Undoing…' : `Undo all ${n}`}
      </button>
      <button className="text-[12px] text-slate-500 hover:text-slate-800" aria-label="Dismiss"
        onClick={() => qc.setQueryData(['last-batch', actor], null)}>✕</button>
      {undo.error && <span className="text-[12px] text-red-700">{(undo.error as Error).message}</span>}
    </div>
  )
}

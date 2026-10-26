// "What changed since I last looked": others' work since you last marked it read - who did what, where -
// opened from the "N new" chip; marking read moves your bookmark to the latest event.
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type WorkEvent } from '../api'
import { fmtTime } from '../format'
import { useSession } from '../session-context'
import { Ref } from './Ref'

const VERB: Record<string, string> = {
  adjust: 'changed', judgment: 'recorded a decision on', signoff: 'signed off', verify: 'verified', note: 'noted on',
  question: 'asked about', answer: 'answered on', review_note: 'left a review note on', resolve_note: 'resolved a review note on',
  attach: 'attached evidence to', undo: 'undid a change on', file: 'filed', assign: 'assigned',
}

function summary(e: WorkEvent): string {
  const p = e.payload as Record<string, unknown>
  const text = p.reason ?? p.decision ?? p.text ?? (p.level ? `${p.level} level` : '') ?? ''
  const value = e.type === 'adjust' && p.new_value !== undefined ? `→ ${Number(p.new_value).toLocaleString('en-US')} ` : ''
  return `${value}${String(text ?? '')}`.slice(0, 120)
}

export function ChangesChip() {
  const { actor, people } = useSession()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const { data } = useQuery({
    queryKey: ['changes', actor],
    queryFn: () => api<{ count: number; events: WorkEvent[] }>('/me/changes'),
    enabled: !actor.startsWith('cu-'), // the firm's change log is internal
  })
  const seen = useMutation({
    mutationFn: (event_id: number) => api('/me/seen', { method: 'POST', body: JSON.stringify({ event_id }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['changes'] }); setOpen(false) },
  })
  if (!data || data.count === 0) return null
  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const events = data.events.slice().reverse()
  return (
    <span className="relative">
      <button onClick={() => setOpen(!open)} className="chip border-indigo-400 bg-indigo-500/20 text-indigo-100 hover:bg-indigo-500/30"
        title="Changes by others since you last looked" aria-label={`${data.count} new changes`}>
        {data.count} new
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 max-h-[70vh] w-[26rem] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-md border border-slate-200 bg-white text-slate-800 shadow-xl">
          <div className="sticky top-0 flex items-center justify-between border-b border-slate-100 bg-white px-3 py-2">
            <span className="text-[12px] font-medium">{data.count} change{data.count > 1 ? 's' : ''} by others since you last looked</span>
            <button className="text-[12px] text-indigo-700 hover:underline" disabled={seen.isPending}
              onClick={() => seen.mutate(Math.max(...data.events.map((e) => e.id)))}>Mark all as read</button>
          </div>
          <ul className="divide-y divide-slate-100 text-[12px]">
            {events.slice(0, 50).map((e) => (
              <li key={e.id} className={`px-3 py-1.5 ${e.undone ? 'opacity-50' : ''}`}>
                <div className="flex items-center gap-1.5">
                  <b>{name(e.actor)}</b> <span>{VERB[e.type] ?? e.type.replace('_', ' ')}</span>
                  {e.target && <Ref id={e.target} />}
                  <span className="ml-auto text-[11px] text-slate-400">{fmtTime(e.at)}</span>
                </div>
                {summary(e) && <div className="text-slate-500">{summary(e)}</div>}
              </li>
            ))}
            {events.length > 50 && <li className="px-3 py-1.5 text-slate-400">… and {events.length - 50} more</li>}
          </ul>
        </div>
      )}
    </span>
  )
}

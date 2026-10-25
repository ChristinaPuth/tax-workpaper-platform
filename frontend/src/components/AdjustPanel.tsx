// Changing a number on the return: the engine value is never overwritten - an adjustment is an event with
// who, why and the estimated tax effect, and undoing it is another event. (Day 4 adds verify / notes / sign-off.)
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Adjustment, type WorkEvent, type WorkingLine } from '../api'
import { fmtEffect, fmtTime, fmtValue } from '../format'
import { useSession } from '../session-context'
import { LOG_DERIVED, useGate } from '../queries'
import { KindBadge } from './ui'

const STALE_NOTE =
  'This line depends on a changed number, but it is computed by an engine formula (tax brackets, limits, ' +
  'phase-outs). The engine value is shown until the return is recomputed; the estimated effect is in the summary.'

export function AdjustPanel({ version, editable, lineKey, engineValue, working, adjustment, proposals }: {
  version: string
  editable: boolean // only the current version can be adjusted; older engine versions are history
  lineKey: string
  engineValue: number | string | null
  working: WorkingLine | undefined
  adjustment: Adjustment | undefined
  proposals: { value: number; label: string }[]
}) {
  const { person, people } = useSession()
  const qc = useQueryClient()
  const target = `line:${version}:${lineKey}`
  const { data: history = [] } = useQuery({
    queryKey: ['events', target],
    queryFn: () => api<WorkEvent[]>(`/events?target=${encodeURIComponent(target)}&type=adjust,undo`),
  })
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  const [open, setOpen] = useState(false)

  const refresh = () => {
    LOG_DERIVED.forEach((key) => qc.invalidateQueries({ queryKey: [key] }))
  }
  const { data: gate } = useGate()
  const layer = gate?.filed ? 'amendment' : 'return' // the filed return is frozen; changes amend it
  const post = useMutation({
    mutationFn: (body: object) => api<WorkEvent>('/events', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      refresh()
      setOpen(false)
      setValue('')
      setReason('')
    },
  })

  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const canAdjust = !!person?.can.includes('adjust')
  const canUndo = (actor: string) => person?.id === actor || ['reviewer', 'partner'].includes(person?.role ?? '')
  const numeric = typeof engineValue === 'number'
  const parsed = Number(value.replace(/[$,\s]/g, ''))
  const valid = value.trim() !== '' && Number.isFinite(parsed) && reason.trim().length > 0
  const adjustEvents = history.filter((e) => e.type === 'adjust')

  return (
    <section className="space-y-2">
      {working?.kind === 'stale' && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-[12px] text-amber-900">
          <KindBadge kind="stale" /> {STALE_NOTE}
        </div>
      )}
      {working?.kind === 'propagated' && (
        <div className="rounded-md border border-sky-200 bg-sky-50 p-2 text-[12px] text-sky-900">
          <KindBadge kind="propagated" partial={working.partial} /> Recomputed from changed inputs with the engine’s own
          arithmetic: {fmtValue(working.engine)} → <b className="num">{fmtValue(working.value)}</b>.
          {working.partial && ' Some inputs are engine formulas awaiting a recompute, so treat it as approximate.'}
        </div>
      )}

      {adjustEvents.length > 0 && (
        <div>
          <div className="section-title mb-1">Changes to this line</div>
          <div className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
            {adjustEvents.map((e) => {
              const active = adjustment?.event_id === e.id
              return (
                <div key={e.id} className={`p-2 ${e.undone ? 'opacity-50' : ''}`}>
                  <div className="flex items-baseline gap-2">
                    <span className="num font-medium">
                      {fmtValue(engineValue)} → {fmtValue(e.payload.new_value as number)}
                    </span>
                    {e.undone && <span className="chip border-slate-200 text-slate-500">undone</span>}
                    {active && <KindBadge kind="adjusted" />}
                    <span className="ml-auto text-[11px] text-slate-400">
                      {name(e.actor)} · {fmtTime(e.at)}
                    </span>
                  </div>
                  <p className="text-slate-600">{String(e.payload.reason ?? '')}</p>
                  {active && adjustment && (
                    <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-500">
                      {adjustment.effect.estimated ? (
                        <span>
                          Estimated effect — federal <b className="num text-slate-700">{fmtEffect(adjustment.effect.federal)}</b>, California{' '}
                          <b className="num text-slate-700">{fmtEffect(adjustment.effect.california)}</b> ({adjustment.effect.category})
                        </span>
                      ) : (
                        <span>{adjustment.effect.category?.includes('payment') ? 'Payment: flows through the balance due directly.' : 'No rate applies — effect not estimated.'}</span>
                      )}
                      {canUndo(e.actor) && (
                        <button
                          className="ml-auto text-indigo-700 hover:underline"
                          onClick={() => post.mutate({ type: 'undo', payload: { event_id: e.id }, layer })}
                        >
                          Undo
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {canAdjust && numeric && editable && (
        <div>
          {!open ? (
            <button className="btn" onClick={() => setOpen(true)}>
              {gate?.filed ? 'Amend this number (1040-X)' : 'Adjust this number'}
            </button>
          ) : (
            <form
              className="space-y-2 rounded-md border border-indigo-200 bg-white p-2.5"
              onSubmit={(e) => {
                e.preventDefault()
                if (valid) post.mutate({ type: 'adjust', target, payload: { new_value: parsed, reason: reason.trim() }, layer })
              }}
            >
              <div className="section-title">{gate?.filed ? 'Amend' : 'Adjust'} {lineKey}</div>
              {proposals.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {proposals.map((p) => (
                    <button
                      type="button"
                      key={p.label}
                      className="chip border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                      onClick={() => {
                        setValue(String(p.value))
                        setReason((r) => r || p.label)
                      }}
                    >
                      Use proposed {fmtValue(p.value)}
                    </button>
                  ))}
                </div>
              )}
              <label className="block">
                <span className="text-[11px] text-slate-500">New value (engine: {fmtValue(engineValue)})</span>
                <input
                  autoFocus
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  inputMode="decimal"
                  className="num mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-[11px] text-slate-500">Why (required — it becomes part of the record)</span>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={2}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1"
                />
              </label>
              {post.error && <p className="text-[12px] text-red-700">{String((post.error as Error).message)}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={!valid || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">
                  Save change
                </button>
                <button type="button" className="btn" onClick={() => setOpen(false)}>
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </section>
  )
}

// Versions: what changed between two states of the return and why. What-if: the engine's own results for
// alternative treatments, with the choice recorded as an election decision.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type Comparison, type SummaryDelta, type WhatIf } from '../api'
import { Ref } from '../components/Ref'
import { Tech } from '../components/Help'
import { FORM_NAME, fmtEffect, fmtTime, fmtValue, formOf } from '../format'
import { useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'

const PRESETS: [string, string, string][] = [
  ['v1', 'v2', 'v1 → v2'],
  ['v2', 'v3', 'v2 → v3'],
  ['v1', 'v3', 'v1 → v3'],
  ['v3', 'working', 'v3 → with adjustments'],
]

export function Versions() {
  const [params, setParams] = useSearchParams()
  const a = params.get('a') ?? 'v2'
  const b = params.get('b') ?? 'v3'
  const set = (na: string, nb: string) => setParams({ tab: 'versions', a: na, b: nb })
  const [q, setQ] = useState('')
  const { data } = useQuery({
    queryKey: ['reports', 'compare', a, b],
    queryFn: () => api<Comparison>(`/compare?a=${a}&b=${b}`),
  })
  const latest = useLatestVersion()
  const lineVersion = b === 'working' ? latest : b
  const rows = (data?.lines ?? []).filter((r) => !q || `${r.key} ${r.label}`.toLowerCase().includes(q.toLowerCase()))
  const byForm = rows.reduce<Record<string, typeof rows>>((m, r) => ((m[r.form] ??= []).push(r), m), {})

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map(([x, y, label]) => (
          <button key={label} onClick={() => set(x, y)}
            className={`btn ${a === x && b === y ? 'border-indigo-400 bg-indigo-50 text-indigo-800' : ''}`}>{label}</button>
        ))}
        <span className="ml-2 text-[12px] text-slate-500">or</span>
        <StateSelect value={a} states={data?.states} onChange={(v) => set(v, b)} label="From" />
        <span className="text-slate-400">→</span>
        <StateSelect value={b} states={data?.states} onChange={(v) => set(a, v)} label="To" />
      </div>
      {!data ? <div className="text-slate-400">Comparing…</div> : (
        <>
          {data.trigger && (
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">
                {data.to === 'amended' ? 'What the amendment changes' : data.to === 'working' ? 'Why it differs' : `Why ${data.to} was computed`}
              </div>
              <p className="text-slate-800">{data.trigger}</p>
              {(data.documents.added.length > 0 || data.documents.removed.length > 0) && (
                <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[12px]">
                  {data.documents.added.length > 0 && <span className="text-slate-500">Documents now used:</span>}
                  {data.documents.added.map((d) => <Ref key={d} id={`doc:${d}`} />)}
                  {data.documents.removed.length > 0 && <span className="ml-2 text-slate-500">No longer used:</span>}
                  {data.documents.removed.map((d) => <Ref key={d} id={`doc:${d}`} />)}
                  {data.documents.superseded.length > 0 && (
                    <span className="ml-2 text-slate-500">({data.documents.superseded.join(', ')} superseded by a corrected document)</span>
                  )}
                </div>
              )}
            </div>
          )}
          <SummaryTable rows={data.summary} from={data.from} to={data.to === 'working' ? 'with adjustments' : data.to} />
          {data.to === 'working' && data.adjustments.length === 0 && (
            <p className="text-slate-500">No adjustments yet - the working return equals {latest}.</p>
          )}
          <section>
            <div className="mb-2 flex flex-wrap items-baseline gap-2">
              <h2 className="font-semibold text-slate-800">Lines that differ</h2>
              <span className="text-[12px] text-slate-500">
                {Object.entries(data.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(' · ') || 'none'}
              </span>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter lines"
                className="ml-auto w-48 rounded-md border border-slate-300 px-2 py-1 text-[12px]" aria-label="Filter lines" />
            </div>
            <div className="space-y-3">
              {Object.entries(byForm).map(([form, rs]) => (
                <div key={form} className="overflow-x-auto rounded-md border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 bg-slate-50 px-3 py-1 text-[12px] font-medium text-slate-600">
                    {FORM_NAME[form] ?? form} <span className="font-normal text-slate-400">· {rs.length}</span>
                  </div>
                  <table className="w-full text-[13px]">
                    <tbody className="divide-y divide-slate-100">
                      {rs.map((r) => (
                        <tr key={r.key}>
                          <td className="px-3 py-1">
                            <Link to={`/return?v=${r.change === 'removed' ? a : lineVersion}&form=${formOf(r.key)}&line=${r.key}`}
                              className="text-slate-800 hover:text-indigo-700 hover:underline">{r.label}</Link>
                            <Tech><span className="ml-1.5 font-mono text-[11px] text-slate-400">{r.key}</span></Tech>
                          </td>
                          <td className="w-28 px-3 py-1 text-right"><ChangeChip change={r.change} /></td>
                          <td className="num w-28 px-3 py-1 text-right text-slate-500">{r.change === 'added' ? '—' : fmtValue(r.old)}</td>
                          <td className="num w-28 px-3 py-1 text-right font-medium text-slate-900">{r.change === 'removed' ? '—' : fmtValue(r.new)}</td>
                          <td className="num w-24 px-3 py-1 text-right text-slate-600">{r.delta === null ? '' : fmtEffect(r.delta)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
              {rows.length === 0 && <p className="text-slate-500">No line differs.</p>}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function StateSelect({ value, states, onChange, label }: { value: string; states?: Comparison['states']; onChange: (v: string) => void; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}
      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-[12px]">
      {(states ?? [{ id: value, label: value, trigger: '' }]).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
    </select>
  )
}

function ChangeChip({ change }: { change: string }) {
  const cls = change === 'added' ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : change === 'removed' ? 'border-red-200 bg-red-50 text-red-700'
      : change === 'needs recompute' ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-slate-200 text-slate-600'
  return <span className={`chip ${cls}`}>{change}</span>
}

function SummaryTable({ rows, from, to }: { rows: SummaryDelta[]; from: string; to: string }) {
  const moved = rows.filter((r) => r.delta)
  if (!moved.length) return null
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
      <table className="w-full text-[13px]">
        <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-1.5 font-medium">Summary</th>
            <th className="px-3 py-1.5 text-right font-medium">{from}</th>
            <th className="px-3 py-1.5 text-right font-medium">{to}</th>
            <th className="px-3 py-1.5 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {moved.map((r) => (
            <tr key={r.jurisdiction + r.key}>
              <td className="px-3 py-1 text-slate-800">{r.label}</td>
              <td className="num px-3 py-1 text-right text-slate-500">{fmtValue(r.old)}</td>
              <td className="num px-3 py-1 text-right font-medium">{r.estimated ? '≈ ' : ''}{fmtValue(r.new)}</td>
              <td className="num px-3 py-1 text-right">{fmtEffect(r.delta)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ------------------------------------------------------------------ what-if
export function WhatIfs() {
  const { data } = useQuery({ queryKey: ['reports', 'what-if'], queryFn: () => api<{ alternatives: WhatIf[] }>('/what-if') })
  if (!data) return <div className="text-slate-400">Loading the alternatives…</div>
  return (
    <div className="space-y-3">
      <p className="text-slate-600">
        The engine's own results for alternative treatments of this return. We cannot rerun the engine, so choosing one is
        recorded as an election (with the authority relied on); the return's numbers change when the engine reruns with it.
      </p>
      {data.alternatives.map((w) => <WhatIfCard key={w.id} w={w} />)}
    </div>
  )
}

function WhatIfCard({ w }: { w: WhatIf }) {
  const [showLines, setShowLines] = useState(false)
  const none = !w.federal && !w.california && !w.penalty
  const better = w.federal + w.california < 0
  return (
    <section className="panel space-y-2 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium text-slate-900">{w.description}</h3>
          <div className="text-[12px] text-slate-500">
            Engine result on {w.base_version}
            {w.findings.length > 0 && <> · used by {w.findings.map((f) => <Link key={f} to={`/findings?id=${f}`} className="text-indigo-700 hover:underline">{f}</Link>)}</>}
          </div>
        </div>
        <div className="text-right text-[12px] leading-tight">
          {none ? <span className="text-slate-500">No change in tax</span> : (
            <>
              <div>Federal <b className="num">{fmtEffect(w.federal)}</b></div>
              <div>California <b className="num">{fmtEffect(w.california)}</b></div>
              {w.penalty ? <div>Penalty <b className="num">{fmtEffect(w.penalty)}</b></div> : null}
              <div className={better ? 'text-emerald-700' : 'text-slate-400'}>{better ? 'saves tax' : 'costs tax'}</div>
            </>
          )}
        </div>
      </div>
      {w.summary.some((s) => s.delta) && <SummaryTable rows={w.summary} from="as filed" to="alternative" />}
      {w.lines.length > 0 && (
        <div>
          <button onClick={() => setShowLines(!showLines)} className="text-[12px] text-indigo-700 hover:underline">
            {showLines ? 'Hide' : 'Show'} the {w.lines.length} lines it changes
          </button>
          {showLines && (
            <ul className="mt-1 max-h-64 overflow-y-auto rounded-md border border-slate-100 text-[12px]">
              {w.lines.map((l) => (
                <li key={l.key} className="flex gap-2 px-2 py-0.5">
                  <span className="min-w-0 flex-1 truncate">{l.label}<Tech><span className="ml-1 font-mono text-slate-400">{l.key}</span></Tech></span>
                  <span className="num text-slate-500 line-through">{fmtValue(l.old)}</span>
                  <span className="num font-medium">{fmtValue(l.new)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Election w={w} />
    </section>
  )
}

function Election({ w }: { w: WhatIf }) {
  const { person, people } = useSession()
  const latest = useLatestVersion()
  const post = usePostEvent()
  const [open, setOpen] = useState(false)
  const [authority, setAuthority] = useState('')
  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const can = !!person?.can.includes('judgment')
  if (w.election) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1.5 text-[12px] text-indigo-900">
        <span className="chip border-indigo-300 bg-white text-indigo-700">elected</span>
        <span>{name(w.election.actor)} on {fmtTime(w.election.at)} - authority: {w.election.authority}</span>
        {(person?.id === w.election.actor || person?.role === 'reviewer' || person?.role === 'partner') && (
          <button className="ml-auto text-indigo-700 hover:underline" disabled={post.isPending}
            onClick={() => post.mutate({ type: 'undo', payload: { event_id: w.election!.event_id } })}>Withdraw</button>
        )}
      </div>
    )
  }
  if (!can) return null
  // a what-if that an issue relies on is that issue's correction, not an optional choice: settle it there
  if (w.findings.length) {
    return (
      <p className="text-[12px] text-slate-600">
        This is the correction proposed by {w.findings.map((f) => <Link key={f} to={`/findings?id=${f}`} className="text-indigo-700 hover:underline">{f}</Link>)} -
        settle it on the issue, not as an election.
      </p>
    )
  }
  if (!open) return <button className="btn" onClick={() => setOpen(true)}>Record this as our election</button>
  return (
    <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => {
      e.preventDefault()
      if (!authority.trim()) return
      post.mutate({ type: 'judgment', target: `ver:${latest}`, payload: {
        kind: 'election', decision: `Elect: ${w.description}`, authority: authority.trim(), what_if: w.id } },
      { onSuccess: () => setOpen(false) })
    }}>
      <input value={authority} onChange={(e) => setAuthority(e.target.value)} placeholder="Authority relied on (required)"
        className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-[12px]" aria-label="Authority" />
      <button type="submit" disabled={!authority.trim() || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">Record election</button>
      <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
      {post.error && <span className="text-[12px] text-red-700">{(post.error as Error).message}</span>}
    </form>
  )
}

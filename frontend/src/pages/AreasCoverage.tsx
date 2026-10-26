// Every area considered: the firm's nine budget areas, what is in each, what is still open there, and the
// preparer's record that it was considered (or does not apply). Partner review is the partner's sign-off.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Ref } from '../components/Ref'
import { fmtTime } from '../format'
import { useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'

type Area = {
  key: string; title: string; budget_hours: number; status: 'open' | 'considered' | 'not_applicable'; by_hand: boolean
  lines: number; documents: number; open_errors: string[]; open_warnings: string[]; reports: string[]
  record: { by: string; at: string; decision: string; authority: string | null } | null
}
type Coverage = { areas: Area[]; left: string[]; summary: { considered: number; total: number } }

const STATUS = {
  open: ['to consider', 'border-amber-200 bg-amber-50 text-amber-800'],
  considered: ['considered', 'border-emerald-200 bg-emerald-50 text-emerald-700'],
  not_applicable: ['not applicable', 'border-slate-200 bg-slate-50 text-slate-600'],
} as const

export function AreasCoverage() {
  const { data } = useQuery({ queryKey: ['coverage', 'events'], queryFn: () => api<Coverage>('/coverage') })
  if (!data) return <div className="p-6 text-slate-400">Working out the areas…</div>
  return (
    <div className="space-y-3">
      <header className={`rounded-lg border p-4 ${data.left.length ? 'border-amber-300 bg-amber-50' : 'border-emerald-300 bg-emerald-50'}`}>
        <h1 className="text-lg font-semibold text-slate-900">Every area considered</h1>
        <p className="text-slate-700">
          {data.summary.considered} of {data.summary.total} areas done. Each of the firm's budget areas is considered,
          or marked not applicable with the reason, before filing. An area with an open error cannot be closed.
        </p>
      </header>
      <ul className="space-y-2">{data.areas.map((a) => <AreaRow key={a.key} a={a} />)}</ul>
    </div>
  )
}

function AreaRow({ a }: { a: Area }) {
  const { person } = useSession()
  const version = useLatestVersion()
  const post = usePostEvent()
  const [open, setOpen] = useState(false)
  const [applies, setApplies] = useState(true)
  const [decision, setDecision] = useState('')
  const [authority, setAuthority] = useState('')
  const can = a.by_hand && !!person?.can.includes('judgment')
  const [label, cls] = STATUS[a.status]
  return (
    <li className="panel p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-medium text-slate-900">{a.title}</span>
        <span className={`chip ${cls}`}>{label}</span>
        <span className="text-[12px] text-slate-500">
          {a.lines} line{a.lines === 1 ? '' : 's'} · {a.documents} document{a.documents === 1 ? '' : 's'} · budget {a.budget_hours} h
        </span>
        <span className="ml-auto flex gap-2 text-[12px]">
          {a.reports.map((r) => <Link key={r} to={`/reports?tab=area&r=${r}`} className="text-indigo-700 hover:underline">{r} report</Link>)}
        </span>
      </div>
      {a.open_errors.length > 0 && (
        <div className="mt-1 flex flex-wrap items-center gap-1 text-[12px]">
          <span className="text-red-700">{a.open_errors.length} open error{a.open_errors.length > 1 ? 's' : ''}:</span>
          {a.open_errors.map((f) => <Ref key={f} id={`finding:${f}`} />)}
        </div>
      )}
      {a.open_warnings.length > 0 && (
        <div className="mt-1 flex flex-wrap items-center gap-1 text-[12px]">
          <span className="text-amber-800">{a.open_warnings.length} open warning{a.open_warnings.length > 1 ? 's' : ''}:</span>
          {a.open_warnings.slice(0, 6).map((f) => <Ref key={f} id={`finding:${f}`} />)}
          {a.open_warnings.length > 6 && <span className="text-slate-400">+{a.open_warnings.length - 6} more</span>}
        </div>
      )}
      {a.record && (
        <p className="mt-1 text-[13px] text-slate-600">
          {a.record.by}, {fmtTime(a.record.at)}: {a.record.decision}{a.record.authority ? ` (basis: ${a.record.authority})` : ''}
        </p>
      )}
      {!a.by_hand && a.status === 'open' && <p className="mt-1 text-[13px] text-slate-500">Done when the partner signs off the whole return.</p>}
      {can && a.status === 'open' && !open && (
        <button className="btn mt-1.5" onClick={() => setOpen(true)}>Record this area</button>
      )}
      {open && (
        <form className="mt-1.5 space-y-1.5 rounded-md border border-indigo-200 bg-white p-2" onSubmit={(e) => {
          e.preventDefault()
          post.mutate({ type: 'judgment', target: `ver:${version}`, payload: { kind: 'area', area: a.key, applies, decision: decision.trim(), authority: authority.trim() } },
            { onSuccess: () => setOpen(false) })
        }}>
          <div className="flex gap-3 text-[13px]">
            <label className="flex items-center gap-1"><input type="radio" checked={applies} onChange={() => setApplies(true)} /> Considered</label>
            <label className="flex items-center gap-1"><input type="radio" checked={!applies} onChange={() => setApplies(false)} /> Not applicable</label>
          </div>
          <textarea value={decision} onChange={(e) => setDecision(e.target.value)} rows={2} aria-label="What was done"
            placeholder={applies ? 'What was reviewed in this area' : 'Why this area does not apply to the clients'}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
          <input value={authority} onChange={(e) => setAuthority(e.target.value)} aria-label="Basis"
            placeholder="Basis: workpapers, documents, engagement letter…" className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
          {post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={!decision.trim() || !authority.trim() || post.isPending}
              className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">Record</button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      )}
    </li>
  )
}

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type Finding, type Severity } from '../api'
import { fmtEffect } from '../format'
import { DecisionForm, Empty, FindingCard } from '../components/ui'
import { useFindingStates } from '../queries'
import { useSession } from '../session-context'

const ORDER: Severity[] = ['error', 'warning', 'info']

// Everything the independent checks raised, worst first. (The working Inbox builds on this.)
export function FindingsPage() {
  const { data: all = [] } = useQuery({ queryKey: ['findings'], queryFn: () => api<Finding[]>('/findings') })
  const [params] = useSearchParams()
  const check = params.get('check') // e.g. P5 from an Inbox group: every finding of that check, any severity
  const id = params.get('id') // one finding, opened from the Inbox when nothing it cites has a page
  const [sev, setSev] = useState<Severity>('error')
  const rows = id ? all.filter((f) => f.id === id)
    : check ? all.filter((f) => f.check.split('-')[0] === check) : all.filter((f) => f.severity === sev)
  const filter = id ?? check
  const { data: states } = useFindingStates()
  const { person } = useSession()
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [bulk, setBulk] = useState(false)
  const openRows = rows.filter((f) => (states?.[f.id]?.state ?? 'open') === 'open')
  const canDecide = !!person?.can.includes('judgment')
  const chosen = rows.filter((f) => picked.has(f.id))
  const toggle = (id: string, on: boolean) => setPicked((p) => { const n = new Set(p); if (on) n.add(id); else n.delete(id); return n })
  const fed = rows.reduce((n, f) => n + (f.federal_effect ?? 0), 0)
  const ca = rows.reduce((n, f) => n + (f.california_effect ?? 0), 0)

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="mr-2 font-semibold text-slate-900">Findings</h1>
        {filter && (
          <span className="chip border-slate-300 bg-slate-50 text-slate-700">
            {id ? id : rows[0]?.check ?? check} · {rows.length}
            <Link to="/findings" className="ml-1 text-slate-400 hover:text-slate-700" aria-label="Clear filter">
              ✕
            </Link>
          </span>
        )}
        {!filter && ORDER.map((s) => (
          <button
            key={s}
            onClick={() => setSev(s)}
            className={`rounded-md px-2 py-0.5 text-xs ${s === sev ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            {s} <span className="num opacity-70">{all.filter((f) => f.severity === s).length}</span>
          </button>
        ))}
        {!filter && sev === 'error' && (
          <span className="ml-auto text-[12px] text-slate-500">
            If all corrected (first-order estimate): federal <b className="num">{fmtEffect(fed)}</b>, California{' '}
            <b className="num">{fmtEffect(ca)}</b>
          </span>
        )}
      </div>
      <div className="mx-auto max-w-4xl space-y-2 p-4">
        {canDecide && openRows.length > 1 && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-white p-2 text-[12px]">
            <span className="text-slate-600">{picked.size} selected</span>
            <button className="btn" onClick={() => setPicked(new Set(openRows.map((f) => f.id)))}>Select all open ({openRows.length})</button>
            <button className="btn" onClick={() => setPicked(new Set())}>Clear</button>
            <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40" disabled={!picked.size} onClick={() => setBulk(true)}>
              One decision for the selected
            </button>
          </div>
        )}
        {bulk && chosen.length > 0 && (
          <DecisionForm findings={chosen} onDone={() => { setBulk(false); setPicked(new Set()) }} />
        )}
        {rows.length === 0 ? <Empty>Nothing here.</Empty> : rows.map((f) => (
          <FindingCard key={f.id} f={f} selected={picked.has(f.id)} onSelect={canDecide && openRows.length > 1 ? (on) => toggle(f.id, on) : undefined} />
        ))}
      </div>
    </div>
  )
}

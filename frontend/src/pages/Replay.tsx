// The season replayed: move through the dates and see the file as it stood - documents in, the current
// version, e-file submissions and their errors, the IRS account, notices and what came next.
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Ref } from '../components/Ref'
import { fmtDate, fmtValue } from '../format'

type Replay = {
  at: string
  stage: string
  key_dates: { date: string; label: string }[]
  timeline: { date: string; event: string; actor: string | null; detail: string | null; refs: string[] }[]
  documents: { received: number; of: number; latest: { id: string; title: string; received: string }[] }
  version: { version: string; computed_at: string; trigger: string; summary: Record<string, Record<string, number>> } | null
  efile: { date: string; jurisdiction: string; status: string; submission_id: string; errors: { code: string; message: string }[] }[]
  filing_status: Record<string, string>
  transcript: { as_of: string; transactions: { date: string; code: string; description: string; amount: unknown }[] } | null
  alerts: { kind: string; text: string; findings?: string[]; document?: string; items?: string[] }[]
  deadlines: { what: string; date: string; passed: boolean }[]
  upcoming: { date: string; label: string }[]
}

// packet references in the timeline (D23, qa-01, msg-07, v3) as node ids
function refId(r: string): string | null {
  if (/^D\d+$/.test(r)) return `doc:${r}`
  if (/^(qa|msg|call)-/.test(r)) return `${r.split('-')[0]}:${r}`
  if (/^v\d+$/.test(r)) return `ver:${r}`
  return null
}

export function Replay() {
  const [params, setParams] = useSearchParams()
  const at = params.get('at') ?? undefined
  const { data } = useQuery({
    queryKey: ['replay', at ?? ''],
    queryFn: () => api<Replay>(`/replay${at ? `?at=${at}` : ''}`),
    placeholderData: (prev) => prev,
  })
  if (!data) return <div className="text-slate-400">Loading the season…</div>
  const dates = data.key_dates
  const i = Math.max(0, dates.findIndex((d) => d.date === data.at))
  const go = (k: number) => setParams({ tab: 'replay', at: dates[Math.min(dates.length - 1, Math.max(0, k))].date })

  return (
    <div className="space-y-4">
      <div className="panel space-y-2 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={() => go(i - 1)} disabled={i === 0} aria-label="Previous date">←</button>
          <input type="date" value={data.at} onChange={(e) => e.target.value && setParams({ tab: 'replay', at: e.target.value })}
            className="rounded-md border border-slate-300 px-2 py-1 text-[13px]" aria-label="Date" />
          <button className="btn" onClick={() => go(i + 1)} disabled={i >= dates.length - 1} aria-label="Next date">→</button>
          <span className="chip border-indigo-300 bg-indigo-50 text-indigo-800">{data.stage}</span>
        </div>
        <input type="range" min={0} max={dates.length - 1} value={i} onChange={(e) => go(Number(e.target.value))}
          className="w-full" aria-label="Season" />
        <div className="text-[12px] text-slate-500">{dates[i]?.label} · {i + 1} of {dates.length} key dates</div>
      </div>

      {data.alerts.map((a, k) => (
        <div key={k} className={`rounded-md border p-3 text-[13px] ${a.kind === 'rejected' ? 'border-red-300 bg-red-50 text-red-900' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>
          <div className="font-medium">{a.kind === 'rejected' ? 'E-file rejected' : a.kind === 'notice' ? 'Notice from the IRS' : 'Deadline'}</div>
          <div>{a.text}</div>
          {a.findings && a.findings.length > 0 && (
            <div className="mt-1">Explained by {a.findings.map((f) => <Link key={f} to={`/findings?id=${f}`} className="font-medium underline">{f}</Link>)}: fix it there, then file again.</div>
          )}
          {a.items && <ul className="ml-4 mt-1 list-disc">{a.items.map((x) => <li key={x}>{x}</li>)}</ul>}
          {a.document && <div className="mt-1"><Ref id={`doc:${a.document}`} /></div>}
        </div>
      ))}

      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Return">
          {data.version ? (
            <>
              <div className="text-[13px]"><b>{data.version.version}</b> computed {fmtDate(data.version.computed_at)}</div>
              <div className="text-[12px] text-slate-500">{data.version.trigger}</div>
              <div className="mt-1 grid grid-cols-2 gap-x-3 text-[12px]">
                <span>Federal balance due</span><span className="num text-right">{fmtValue(data.version.summary.federal.balance_due)}</span>
                <span>California balance due</span><span className="num text-right">{fmtValue(data.version.summary.california.balance_due)}</span>
              </div>
            </>
          ) : <span className="text-slate-400">Not computed yet</span>}
        </Card>
        <Card title={`Documents · ${data.documents.received} of ${data.documents.of}`}>
          <ul className="space-y-0.5 text-[12px]">
            {data.documents.latest.slice().reverse().map((d) => (
              <li key={d.id} className="flex gap-2"><Ref id={`doc:${d.id}`} /><span className="min-w-0 flex-1 truncate">{d.title}</span><span className="text-slate-400">{fmtDate(d.received)}</span></li>
            ))}
          </ul>
        </Card>
        <Card title="E-file">
          {data.efile.length === 0 ? <span className="text-slate-400">Nothing submitted yet</span> : (
            <ul className="space-y-1 text-[12px]">
              {data.efile.map((e) => (
                <li key={e.submission_id}>
                  <span className={`chip ${e.status === 'accepted' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}`}>{e.status.replace('_', ' ')}</span>{' '}
                  {e.jurisdiction} · {fmtDate(e.date)}
                  {e.errors.map((x) => <div key={x.code} className="ml-2 text-slate-600">{x.code}: {x.message}</div>)}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={data.transcript ? `IRS account as of ${fmtDate(data.transcript.as_of)}` : 'IRS account'}>
          {data.transcript ? (
            <ul className="space-y-0.5 text-[12px]">
              {data.transcript.transactions.map((t, k) => (
                <li key={k} className="flex gap-2"><span className="w-20 text-slate-500">{fmtDate(t.date)}</span><span className="w-10 font-mono">{t.code}</span>
                  <span className="min-w-0 flex-1">{t.description}</span><span className="num">{typeof t.amount === 'number' ? fmtValue(t.amount) : ''}</span></li>
              ))}
            </ul>
          ) : <span className="text-slate-400">Not pulled yet</span>}
        </Card>
        <Card title="Deadlines">
          <ul className="space-y-0.5 text-[12px]">
            {data.deadlines.map((d) => (
              <li key={d.what} className={d.passed ? 'text-slate-400' : 'text-slate-800'}>{fmtDate(d.date)} · {d.what}{d.passed ? ' (passed)' : ''}</li>
            ))}
          </ul>
        </Card>
        <Card title="What happened so far">
          <ol className="max-h-56 space-y-0.5 overflow-y-auto text-[12px]">
            {data.timeline.slice().reverse().map((t, k) => (
              <li key={k}>
                <span className="text-slate-500">{fmtDate(t.date)}</span> · {t.event}
                {t.refs.map((r) => { const id = refId(r); return id ? <Ref key={r} id={id} className="ml-1" /> : null })}
                {t.detail && <div className="ml-4 text-slate-500">{t.detail}</div>}
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-3">
      <div className="section-title mb-1">{title}</div>
      {children}
    </section>
  )
}

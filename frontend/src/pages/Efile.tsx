// E-file acknowledgments: what the IRS and the FTB said about each submission. The partner records each one;
// a federal rejection puts the return back in preparation (see the banner on Can we file?).
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type EfileAck, type Gate } from '../api'
import { fmtTime } from '../format'
import { useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'

const STATUS: Record<EfileAck['status'], string> = {
  accepted: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  rejected: 'border-red-200 bg-red-50 text-red-700',
  not_transmitted: 'border-slate-200 bg-slate-50 text-slate-600',
}
const label = (s: string) => s.replace('_', ' ')

export function Efile({ gate }: { gate: Gate }) {
  const { person } = useSession()
  const can = !!person?.can.includes('efile')
  return (
    <section className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold text-slate-800">E-file acknowledgments</h2>
      {gate.acks.length === 0 && <p className="text-[13px] text-slate-500">None recorded yet.</p>}
      <ul className="divide-y divide-slate-100">
        {gate.acks.map((a) => (
          <li key={a.event_id} className="py-1.5 text-[13px]">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium capitalize text-slate-900">{a.jurisdiction}</span>
              <span className={`chip ${STATUS[a.status]}`}>{label(a.status)}</span>
              {a.submission_id && <span className="font-mono text-[11px] text-slate-400">{a.submission_id}</span>}
              <span className="ml-auto text-[11px] text-slate-400">
                {a.received ? `${fmtTime(a.received)} · ` : ''}recorded by {a.by_name}{a.at ? `, ${fmtTime(a.at)}` : ''}
              </span>
            </div>
            {a.errors?.map((e) => <div key={e.code} className="text-red-800"><span className="font-mono">{e.code}</span>: {e.message}</div>)}
          </li>
        ))}
      </ul>
      {can && (gate.filed || gate.rejected) && <RecordAck gate={gate} />}
    </section>
  )
}

// The agency's acknowledgments as they arrive (here: the packet's e-file records), offered one at a time.
function RecordAck({ gate }: { gate: Gate }) {
  const version = useLatestVersion()
  const post = usePostEvent()
  const [chosen, setChosen] = useState('')
  const { data: records = [] } = useQuery({ queryKey: ['efile-records'], queryFn: () => api<EfileAck[]>('/efile/records') })
  const recorded = new Set(gate.acks.map((a) => a.submission_id))
  const waiting = records.filter((r) => !recorded.has(r.submission_id))
  if (!waiting.length) return null
  const r = waiting.find((x) => x.submission_id === chosen) ?? waiting[0]
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 text-[13px]">
      <span className="text-slate-600">Acknowledgment received:</span>
      <select value={r.submission_id} onChange={(e) => setChosen(e.target.value)} aria-label="Acknowledgment"
        className="rounded-md border border-slate-300 px-2 py-1 text-[12px]">
        {waiting.map((x) => (
          <option key={x.submission_id} value={x.submission_id}>
            {x.date?.slice(0, 10)} {x.jurisdiction} {label(x.status)}{x.errors?.length ? ` (${x.errors[0].code})` : ''}
          </option>
        ))}
      </select>
      <button className="btn" disabled={post.isPending} onClick={() => post.mutate({
        type: 'efile', target: `ver:${version}`,
        payload: { jurisdiction: r.jurisdiction, status: r.status, submission_id: r.submission_id, errors: r.errors ?? [], received: r.date },
      })}>Record</button>
      {post.error && <span className="text-[12px] text-red-700">{(post.error as Error).message}</span>}
    </div>
  )
}

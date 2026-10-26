// A corrected document and the one it replaces: every value the correction changed, and the lines that used
// the old value and use the new one in each return version.
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { fmtDate, fmtValue } from '../format'
import { Ref } from './Ref'

type Change = { page: number; field: string; label: string | null; before: unknown; after: unknown; before_ev: string | null; after_ev: string | null;
  used_before: Record<string, string[]>; used_after: Record<string, string[]> }
type Correction = { original: { id: string; title: string; received_at: string }; corrected: { id: string; title: string; received_at: string };
  values_compared: number; changes: Change[]; superseded_in: string[] }

// each line once, opened in the latest version that has it, with the versions it is in
function where(u: Record<string, string[]>) {
  const m = new Map<string, string[]>()
  Object.entries(u).forEach(([v, ks]) => ks.forEach((k) => m.set(k, [...(m.get(k) ?? []), v])))
  return [...m.entries()].map(([k, vs]) => (
    <span key={k} className="inline-flex items-center gap-1"><Ref id={`line:${vs[vs.length - 1]}:${k}`} /><span className="text-[11px] text-slate-400">{vs.join(', ')}</span></span>
  ))
}
const same = (a: Record<string, string[]>, b: Record<string, string[]>) =>
  JSON.stringify([...new Set(Object.values(a).flat())].sort()) === JSON.stringify([...new Set(Object.values(b).flat())].sort())

export function CorrectionDiff({ docId, corrected }: { docId: string; corrected: boolean }) {
  const { data } = useQuery({ queryKey: ['correction', docId], queryFn: () => api<Correction>(`/documents/${docId}/correction`), retry: false })
  if (!data) return null
  const other = corrected ? data.original : data.corrected
  return (
    <section>
      <div className="section-title mb-1">{corrected ? 'What this correction changed' : 'Replaced by a corrected document'}</div>
      <div className="space-y-1.5 rounded-md border border-sky-200 bg-white p-2.5 text-[12px]">
        <p className="text-slate-600">
          {corrected ? 'Corrects' : 'Corrected by'}{' '}
          <Link to={`/documents/${other.id}`} className="font-medium text-indigo-700 hover:underline">{other.id}</Link>{' '}
          (received {fmtDate(other.received_at)}). {data.changes.length} of {data.values_compared} values differ
          {data.superseded_in.length ? `; the original is set aside from ${data.superseded_in[0]} on` : ''}.
        </p>
        <table className="w-full">
          <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr><th className="py-0.5">Value</th><th className="py-0.5 text-right">Original</th><th className="py-0.5 text-right">Corrected</th><th className="py-0.5 pl-2">Used on</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.changes.map((c) => (
              <tr key={c.page + c.field} className="align-top">
                <td className="py-1">{c.label ?? c.field}<div className="text-[11px] text-slate-400">page {c.page}</div></td>
                <td className="num py-1 text-right text-slate-500 line-through">{fmtValue(c.before)}</td>
                <td className="num py-1 text-right font-medium">{fmtValue(c.after)}</td>
                <td className="py-1 pl-2">
                  <div className="flex flex-wrap gap-1">{where(c.used_after)}</div>
                  {Object.keys(c.used_before).length > 0 && !same(c.used_before, c.used_after) && (
                    <div className="mt-0.5 flex flex-wrap items-center gap-1 text-slate-400">was {where(c.used_before)}</div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

// Answering a tax notice: for each item the notice asks about, what the record holds - the lines as filed,
// the amounts reconciled to source documents, issues and how they were settled, sign-offs, client answers,
// and the documents themselves - with a one-click export to print or attach.
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, requestHeaders } from '../api'
import { Ref } from '../components/Ref'
import { fmtDate, fmtValue } from '../format'
import { useSession } from '../session-context'

type Pack = {
  notice: { id: string; agency: string; type: string; tax_year: number; dated: string; response_due?: string; document?: string }
  version: string
  filed: string | null
  items: {
    text: string
    lines: { key: string; label: string; engine: unknown; as_filed: unknown }[]
    reconciliation: { amount: number; agrees: boolean; document_type: string | null; documents: string[]; total: number | null }[]
    issues: { finding: string; title: string; severity: string; state: string; history: { type: string; by: string; at: string; what: string; authority: string | null; layer: string }[] }[]
    signoffs: { level: string; by: string; at: string; valid: boolean; target: string }[]
    client: string[]
    documents: { id: string; title: string; received: string }[]
  }[]
  client_text: Record<string, string>
}

export function NoticePage() {
  const { id = '' } = useParams()
  const { person } = useSession()
  const { data } = useQuery({ queryKey: ['notice', id], queryFn: () => api<Pack>(`/notices/${id}/pack`) })
  const [downloading, setDownloading] = useState(false)
  if (!data) return <div className="p-6 text-slate-400">Building the evidence pack…</div>
  const n = data.notice
  const open = data.items.flatMap((i) => i.issues).filter((t) => t.state === 'open')

  const download = async () => {
    setDownloading(true)
    try {
      const res = await fetch(`/api/notices/${id}/pack.html`, { headers: requestHeaders() })
      const url = URL.createObjectURL(await res.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = `evidence-pack-${id}.html`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-5 p-6">
        <header className="space-y-1">
          <h1 className="text-lg font-semibold text-slate-900">{n.agency} {n.type}</h1>
          <p className="text-slate-600">
            Tax year {n.tax_year} · dated {fmtDate(n.dated)} · response due <b>{n.response_due ? fmtDate(n.response_due) : '—'}</b>
            {n.document && <> · <Ref id={`doc:${n.document}`} /></>}
            {data.filed ? ` · return filed ${fmtDate(data.filed)}` : ''}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700" onClick={download} disabled={downloading}>
              Download evidence pack
            </button>
            <span className="text-[12px] text-slate-500">
              {person?.sensitive_data_clearance ? 'Unmasked for the response - the export is logged.' : 'Masked: you have no sensitive-data clearance.'}
            </span>
          </div>
          {open.length > 0 && (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-[13px] text-amber-900">
              {open.length} issue{open.length > 1 ? 's' : ''} on these items {open.length > 1 ? 'are' : 'is'} still open
              ({open.map((t) => t.finding).join(', ')}). Settle {open.length > 1 ? 'them' : 'it'} - on an amendment if the return is filed - before answering.
            </p>
          )}
        </header>

        {data.items.map((item, i) => (
          <section key={i} className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="font-semibold text-slate-900">Item {i + 1}: {item.text}</h2>
            <table className="w-full text-[13px]">
              <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <tr><th className="py-1">Line</th><th className="py-1 text-right">As filed</th><th className="py-1 text-right">Engine</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {item.lines.map((l) => (
                  <tr key={l.key}>
                    <td className="py-1"><Link to={`/return?v=${data.version}&form=${l.key.split('.')[0]}&line=${l.key}`} className="hover:text-indigo-700 hover:underline">{l.label}</Link></td>
                    <td className="num py-1 text-right font-medium">{fmtValue(l.as_filed)}</td>
                    <td className="num py-1 text-right text-slate-500">{fmtValue(l.engine)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {item.reconciliation.length > 0 && (
              <ul className="space-y-0.5 text-[13px]">
                {item.reconciliation.map((r) => (
                  <li key={r.amount} className={r.agrees ? 'text-emerald-800' : 'text-red-800'}>
                    {r.agrees ? '✓' : '✗'} {fmtValue(r.amount)}{' '}
                    {r.agrees ? <>= {r.documents.length} × {r.document_type} {r.documents.map((d) => <Ref key={d} id={`doc:${d}`} className="ml-1" />)}</> : 'has no matching set of source documents'}
                  </li>
                ))}
              </ul>
            )}
            {item.issues.map((t) => (
              <div key={t.finding} className="rounded-md border border-slate-200 p-2 text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/findings?id=${t.finding}`} className="font-medium text-slate-900 hover:underline">{t.finding} {t.title}</Link>
                  <span className={`chip ${t.state === 'open' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{t.state}</span>
                </div>
                {t.history.length > 0 && (
                  <ul className="ml-4 mt-1 list-disc text-[12px] text-slate-600">
                    {t.history.map((h, k) => <li key={k}>{fmtDate(h.at)} {h.by}: {h.what}{h.authority ? ` (authority: ${h.authority})` : ''}{h.layer === 'amendment' ? ' · amendment' : ''}</li>)}
                  </ul>
                )}
              </div>
            ))}
            {item.signoffs.length > 0 && (
              <p className="text-[12px] text-slate-600">Signed off: {item.signoffs.map((s) => `${s.level} ${s.by} (${s.valid ? 'holds' : 'reopened'})`).join(' · ')}</p>
            )}
            {item.client.length > 0 && (
              <ul className="text-[12px] text-slate-600">{item.client.map((c) => <li key={c}><b>{c}</b>: {data.client_text[c]}</li>)}</ul>
            )}
            <div className="flex flex-wrap gap-1">
              <span className="text-[12px] text-slate-500">Source documents:</span>
              {item.documents.map((d) => <Ref key={d.id} id={`doc:${d.id}`} />)}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

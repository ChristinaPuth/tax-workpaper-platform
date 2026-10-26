// One area of the return, block by block: the lines (engine and working values, open issues), Schedule CA
// columns side by side, every K-1 box and where it lands, and limits recomputed next to the engine.
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Ref } from '../components/Ref'
import { Tech } from '../components/Help'
import { KindBadge } from '../components/ui'
import { fmtDate, fmtValue, formOf } from '../format'

export const AREA_REPORTS: [string, string][] = [
  ['rentals', 'Rentals & passive losses'],
  ['deductions', 'Deductions, credits & limits'],
  ['k1', 'K-1s & S corporation basis'],
  ['state', 'State split'],
  ['tax', 'Tax computation'],
  ['depreciation', 'Depreciation by asset'],
  ['carryovers', 'Carryovers'],
  ['books', 'Books to tax'],
  ['retirement', 'Retirement & foreign'],
  ['prior', 'Prior preparer vs this year'],
  ['payments', 'Payments'],
  ['rollforward', 'Roll forward to 2026'],
  ['outside', 'Outside filings'],
]

type Issue = { id: string; title: string; severity: string; state: string }
type Row = { key: string; label: string; engine: unknown; working: unknown; kind: string | null; sources: string[]; issues: Issue[] }
type Check = { label: string; engine: unknown; independent: unknown; agrees: boolean; note: string; limit: string | null }
type Block =
  | { type: 'lines'; title: string; note: string | null; rows: Row[] }
  | { type: 'checks'; title: string; rows: Check[] }
  | { type: 'k1'; title: string; document: string; received: string; used: boolean; note: string | null
      rows: { ev: string; field: string; label: string; value: unknown; lines: { key: string; label: string }[] }[] }
  | { type: 'table'; title: string; columns: string[]; column_labels: Record<string, string>
      rows: { line: string; label: string; cols: Record<string, { key: string; value: unknown; issues: string[] }>; ca_share: number | null }[] }
  | { type: 'residency'; title: string; note: string; rows: { state: string; from: string; to: string; status: string }[] }
  | { type: 'grid'; title: string; note: string | null; columns: { key: string; label: string; num: boolean }[]; rows: (Record<string, unknown> & { link?: string })[] }
  | { type: 'issues'; title: string; note: string | null; rows: { id: string; title: string; severity: string; state: string }[] }
  | { type: 'memo'; title: string; note: string | null; rows: { text: string; issues: { id: string; title: string; severity: string; state: string }[]; documents: { id: string; title: string; received: string }[] }[] }

export function AreaReports() {
  const [params, setParams] = useSearchParams()
  const name = AREA_REPORTS.find(([k]) => k === params.get('r'))?.[0] ?? 'rentals'
  const { data } = useQuery({
    queryKey: ['reports', 'area', name],
    queryFn: () => api<{ title: string; version: string; blocks: Block[]; issues: string[] }>(`/reports/area/${name}`),
  })
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1">
        {AREA_REPORTS.map(([k, label]) => (
          <button key={k} onClick={() => setParams({ tab: 'area', r: k })}
            className={`btn ${k === name ? 'border-indigo-400 bg-indigo-50 text-indigo-800' : ''}`}>{label}</button>
        ))}
      </div>
      {!data ? <div className="text-slate-400">Loading the report…</div> : (
        <>
          {data.issues.length > 0 && (
            <p className="text-[12px] text-slate-600">
              Issues raised in this area:{' '}
              {data.issues.map((id) => <Link key={id} to={`/findings?id=${id}`} className="mr-1.5 text-indigo-700 hover:underline">{id}</Link>)}
            </p>
          )}
          {data.blocks.map((b, i) => <BlockView key={i} b={b} version={data.version} />)}
        </>
      )}
    </div>
  )
}

function BlockView({ b, version }: { b: Block; version: string }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white">
      <div className="border-b border-slate-100 bg-slate-50 px-3 py-1.5 font-medium text-slate-800">{b.title}</div>
      {'note' in b && b.note && <p className="px-3 pt-2 text-[12px] text-slate-600">{b.note}</p>}
      <div className="overflow-x-auto p-1">
        {b.type === 'lines' && <LinesTable rows={b.rows} version={version} />}
        {b.type === 'checks' && <ChecksTable rows={b.rows} />}
        {b.type === 'k1' && <K1Table b={b} version={version} />}
        {b.type === 'table' && <ColumnsTable b={b} version={version} />}
        {b.type === 'grid' && <GridTable b={b} />}
        {b.type === 'issues' && (
          <ul className="px-2 py-1 text-[13px]">
            {b.rows.map((r) => <li key={r.id} className="py-0.5"><IssueChip i={r} /> <Link to={`/findings?id=${r.id}`} className="hover:underline">{r.title}</Link></li>)}
          </ul>
        )}
        {b.type === 'memo' && (
          <ul className="divide-y divide-slate-100 text-[13px]">
            {b.rows.map((r, k) => (
              <li key={k} className="px-2 py-1.5">
                <div className="text-slate-800">{r.text}</div>
                {(r.issues.length > 0 || r.documents.length > 0) && (
                  <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[12px] text-slate-500">
                    <span>This year:</span>
                    {r.issues.map((i) => <Link key={i.id} to={`/findings?id=${i.id}`} title={i.title} className="hover:underline"><IssueChip i={i} /> {i.id}</Link>)}
                    {r.documents.map((d) => <Ref key={d.id} id={`doc:${d.id}`} />)}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {b.type === 'residency' && (
          <ul className="px-2 py-1 text-[13px]">
            {b.rows.map((r) => <li key={r.state}>{r.state} {r.status}: {fmtDate(r.from)} - {fmtDate(r.to)}</li>)}
          </ul>
        )}
      </div>
    </section>
  )
}

const lineHref = (version: string, key: string) => `/return?v=${version}&form=${formOf(key)}&line=${key}`

function LinesTable({ rows, version }: { rows: Row[]; version: string }) {
  return (
    <table className="w-full text-[13px]">
      <tbody className="divide-y divide-slate-100">
        {rows.map((r) => (
          <tr key={r.key}>
            <td className="px-2 py-1">
              <Link to={lineHref(version, r.key)} className="text-slate-800 hover:text-indigo-700 hover:underline">{r.label}</Link>
              <Tech><span className="ml-1.5 font-mono text-[11px] text-slate-400">{r.key}</span></Tech>
              {r.issues.map((i) => (
                <Link key={i.id} to={`/findings?id=${i.id}`} title={i.title}
                  className={`chip ml-1.5 ${i.state !== 'open' ? 'border-slate-300 bg-slate-100 text-slate-600'
                    : i.severity === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
                  {i.state !== 'open' ? 'handled' : i.severity}
                </Link>
              ))}
            </td>
            <td className="w-28 px-2 py-1 text-right">{r.kind && <KindBadge kind={r.kind} />}</td>
            <td className="num w-32 px-2 py-1 text-right">
              <span className={r.working !== r.engine ? 'font-medium text-indigo-800' : 'text-slate-900'}>{fmtValue(r.working)}</span>
              {r.working !== r.engine && <div className="text-[11px] text-slate-400 line-through">{fmtValue(r.engine)}</div>}
            </td>
            <td className="hidden w-40 px-2 py-1 md:table-cell">{r.sources.slice(0, 2).map((s) => <Ref key={s} id={`ev:${s}`} />)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ChecksTable({ rows }: { rows: Check[] }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
        <tr><th className="px-2 py-1 font-medium">Check</th><th className="px-2 py-1 text-right font-medium">Engine</th>
          <th className="px-2 py-1 text-right font-medium">Recomputed</th><th className="px-2 py-1" /></tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r) => (
          <tr key={r.label}>
            <td className="px-2 py-1">
              <div className="text-slate-800">{r.label}{r.limit && <span className="ml-1.5 text-[11px] text-slate-400">limit {r.limit}</span>}</div>
              <div className="text-[12px] text-slate-500">{r.note}</div>
            </td>
            <td className="num px-2 py-1 text-right align-top">{fmtValue(r.engine)}</td>
            <td className="num px-2 py-1 text-right align-top">{fmtValue(r.independent)}</td>
            <td className="px-2 py-1 align-top">
              <span className={`chip ${r.agrees ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
                {r.agrees ? '✓ agrees' : '✗ differs'}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function K1Table({ b, version }: { b: Extract<Block, { type: 'k1' }>; version: string }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 px-2 py-1 text-[12px] text-slate-500">
        <Ref id={`doc:${b.document}`} /> received {fmtDate(b.received)} {b.used ? '' : '· not used in the return'}
      </div>
      <table className="w-full text-[13px]">
        <tbody className="divide-y divide-slate-100">
          {b.rows.map((r) => (
            <tr key={r.ev}>
              <td className="px-2 py-1"><Link to={`/value/${r.ev}`} className="text-slate-800 hover:text-indigo-700 hover:underline">{r.label}</Link></td>
              <td className="num w-28 px-2 py-1 text-right">{fmtValue(r.value)}</td>
              <td className="px-2 py-1 text-[12px]">
                {r.lines.length ? r.lines.map((l) => (
                  <Link key={l.key} to={lineHref(version, l.key)} className="mr-2 text-indigo-700 hover:underline">→ {l.label}</Link>
                )) : <span className="text-slate-400">not on a return line</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function ColumnsTable({ b, version }: { b: Extract<Block, { type: 'table' }>; version: string }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-2 py-1 font-medium">Line</th>
          {b.columns.map((c) => <th key={c} className="px-2 py-1 text-right font-medium">{c} · {b.column_labels[c]}</th>)}
          <th className="px-2 py-1 text-right font-medium">CA share</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {b.rows.map((r) => (
          <tr key={r.line}>
            <td className="px-2 py-1 text-slate-800">{r.line} · {r.label}</td>
            {b.columns.map((c) => {
              const cell = r.cols[c]
              return (
                <td key={c} className="num px-2 py-1 text-right">
                  {cell ? (
                    <Link to={lineHref(version, cell.key)} className={`hover:underline ${cell.issues.length ? 'font-medium text-red-700' : 'text-slate-800'}`}
                      title={cell.issues.length ? `Issue ${cell.issues.join(', ')}` : undefined}>{fmtValue(cell.value)}</Link>
                  ) : <span className="text-slate-300">—</span>}
                </td>
              )
            })}
            <td className="num px-2 py-1 text-right text-slate-500">{r.ca_share === null ? '—' : `${Math.round(r.ca_share * 100)}%`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// for the Areas cards: which detailed report covers an area
export const AREA_REPORT_FOR: Record<string, string> = { rentals: 'rentals', deductions: 'deductions', passthroughs: 'k1', california: 'state', business: 'books', totals: 'tax', payments: 'payments' }

function IssueChip({ i }: { i: { severity: string; state: string } }) {
  const cls = i.state !== 'open' ? 'border-slate-300 bg-slate-100 text-slate-600'
    : i.severity === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'
  return <span className={`chip ${cls}`}>{i.state !== 'open' ? 'handled' : i.severity}</span>
}

function GridTable({ b }: { b: Extract<Block, { type: 'grid' }> }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
        <tr>{b.columns.map((c) => <th key={c.key} className={`px-2 py-1 font-medium ${c.num ? 'text-right' : ''}`}>{c.label}</th>)}</tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {b.rows.map((r, k) => (
          <tr key={k}>
            {b.columns.map((c, j) => {
              const v = r[c.key]
              const diff = c.key === 'difference' && typeof v === 'number' && v !== 0
              return (
                <td key={c.key} className={`px-2 py-1 ${c.num ? 'num text-right' : ''} ${diff ? 'font-medium text-amber-800' : ''}`}>
                  {j === 0 && r.link ? <Ref id={r.link}>{fmtValue(v)}</Ref> : v === null || v === undefined || v === '' ? <span className="text-slate-300">—</span> : fmtValue(v)}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

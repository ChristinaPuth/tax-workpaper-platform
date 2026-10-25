// CPA reports: the return against last year, one card per area, and every reconciliation. All of it is
// derived on the server from the packet, the findings and the log - so it always shows the working return.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { AreaCard, ReconciliationGroup, SummaryReport, SummaryRow } from '../api'
import { Ref } from '../components/Ref'
import { fmtDate, fmtEffect, fmtValue, formOf } from '../format'
import { useReport } from '../queries'
import { Tech, Term } from '../components/Help'
import { useMarkVisited } from '../queries'
import { Versions, WhatIfs } from './VersionsWhatIf'
import { AreaReports, AREA_REPORT_FOR } from './AreaReport'

const TABS = [
  ['summary', 'Summary vs 2024'],
  ['areas', 'Areas'],
  ['reconciliations', 'Reconciliations'],
  ['area', 'Area reports'],
  ['versions', 'Versions'],
  ['whatif', 'What-if'],
] as const
type Tab = (typeof TABS)[number][0]

export function ReportsPage() {
  useMarkVisited('reports')
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find(([k]) => k === params.get('tab'))?.[0] ?? 'summary') as Tab
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl p-6">
        <div className="mb-4 flex flex-wrap items-center gap-1 border-b border-slate-200">
          {TABS.map(([k, label]) => (
            <button key={k} onClick={() => setParams({ tab: k })}
              className={`-mb-px border-b-2 px-3 py-1.5 text-[13px] font-medium ${tab === k ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>
        {tab === 'summary' && <Summary />}
        {tab === 'areas' && <Areas />}
        {tab === 'reconciliations' && <Reconciliations />}
        {tab === 'area' && <AreaReports />}
        {tab === 'versions' && <Versions />}
        {tab === 'whatif' && <WhatIfs />}
      </div>
    </div>
  )
}

const lineHref = (version: string, key: string) => `/return?v=${version}&form=${formOf(key)}&line=${key}`

// ------------------------------------------------------------------ summary vs last year
function Summary() {
  const { data } = useReport<SummaryReport>('summary')
  if (!data) return <div className="text-slate-400">Loading the summary…</div>
  return (
    <div className="space-y-6">
      <p className="text-slate-600">
        2025 with everyone's changes applied, against the 2024 return as filed ({data.prior_prepared_by}, filed{' '}
        {fmtDate(data.prior_filed)}). Lines that moved more than the firm threshold ({Math.round(data.threshold.pct * 100)}% and{' '}
        {fmtValue(data.threshold.abs)}) need an explanation.
      </p>
      {data.sections.map((s) => (
        <section key={s.key}>
          <h2 className="mb-1 font-semibold text-slate-800">{s.title}</h2>
          {s.note && <p className="mb-2 text-[12px] text-amber-800">{s.note}</p>}
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="w-full text-[13px]">
              <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-1.5 font-medium">Line</th>
                  <th className="px-3 py-1.5 text-right font-medium">2024</th>
                  <th className="px-3 py-1.5 text-right font-medium">2025</th>
                  <th className="px-3 py-1.5 text-right font-medium">Change</th>
                  <th className="px-3 py-1.5 text-right font-medium">%</th>
                  <th className="px-3 py-1.5 font-medium"><Term t="Prior-year variance">Variance</Term></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {s.rows.map((r) => <SummaryLine key={r.key + r.label} r={r} version={data.version} />)}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

function SummaryLine({ r, version }: { r: SummaryRow; version: string }) {
  return (
    <tr className={r.over_threshold && r.finding_state === 'open' ? 'bg-amber-50/40' : ''}>
      <td className="px-3 py-1.5">
        <Link to={lineHref(version, r.key)} className="text-slate-800 hover:text-indigo-700 hover:underline">{r.label}</Link>
        <Tech><span className="ml-1.5 font-mono text-[11px] text-slate-400">{r.key}</span></Tech>
      </td>
      <td className="num px-3 py-1.5 text-right text-slate-600">
        {r.prior_source ? (
          <Link to={`/value/${r.prior_source}`} className="hover:text-indigo-700 hover:underline" title={`2024 ${r.prior_key} as filed`}>
            {fmtValue(r.prior)}
          </Link>
        ) : fmtValue(r.prior)}
      </td>
      <td className="num px-3 py-1.5 text-right">
        <span className={r.adjusted ? 'font-medium text-indigo-800' : 'text-slate-900'}>{fmtValue(r.working)}</span>
        {r.adjusted && <div className="text-[11px] text-slate-400 line-through">{fmtValue(r.engine)}</div>}
      </td>
      <td className="num px-3 py-1.5 text-right text-slate-700">{fmtEffect(r.change)}</td>
      <td className="num px-3 py-1.5 text-right text-slate-500">{r.pct === null ? '—' : `${r.pct > 0 ? '+' : ''}${Math.round(r.pct * 100)}%`}</td>
      <td className="px-3 py-1.5">
        {r.finding_id ? (
          <Link to={`/findings?id=${r.finding_id}`} className="inline-flex items-center gap-1.5 hover:underline">
            <VarianceChip state={r.finding_state} />
            <span className="font-mono text-[11px] text-slate-400">{r.finding_id}</span>
          </Link>
        ) : r.over_threshold ? (
          <span className="chip border-slate-200 text-slate-500" title="Over the threshold, but last year's line is not the same measure">over threshold</span>
        ) : null}
      </td>
    </tr>
  )
}

function VarianceChip({ state }: { state: SummaryRow['finding_state'] }) {
  if (state === 'reviewed') return <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">✓ explained</span>
  if (state && state !== 'open') return <span className="chip border-slate-300 bg-slate-100 text-slate-600">explained · waiting for review</span>
  return <span className="chip border-amber-200 bg-amber-50 text-amber-800">needs explanation</span>
}

// ------------------------------------------------------------------ areas
const AREA_STATUS: Record<AreaCard['status'], { label: string; cls: string }> = {
  errors: { label: 'errors open', cls: 'border-red-200 bg-red-50 text-red-700' },
  warnings: { label: 'warnings open', cls: 'border-amber-200 bg-amber-50 text-amber-800' },
  review: { label: 'waiting for review', cls: 'border-slate-300 bg-slate-100 text-slate-600' },
  clear: { label: 'clear', cls: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
}

function Areas() {
  const { data } = useReport<AreaCard[]>('areas')
  if (!data) return <div className="text-slate-400">Loading the areas…</div>
  return (
    <div className="space-y-3">
      <p className="text-slate-600">
        Each area of the return: what is still open and what it would change, what has been handled or reviewed, and the
        firm's time budget.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {data.map((a) => <Area key={a.key} a={a} />)}
      </div>
    </div>
  )
}

function Area({ a }: { a: AreaCard }) {
  const st = AREA_STATUS[a.status]
  const open = a.open.error + a.open.warning
  const openEffect = a.open_effect.federal !== 0 || a.open_effect.california !== 0  // identity and variances have none
  return (
    <div className="panel space-y-2 p-3">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-slate-900">{a.label}</h3>
          <div className="text-[12px] text-slate-500">
            {a.documents} document{a.documents === 1 ? '' : 's'}
            {a.budget_hours !== null && ` · budget ${a.budget_hours} h`}
          </div>
        </div>
        <span className={`chip ${st.cls}`}>{st.label}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-[12px]">
        <Stat label="Open" value={open ? `${a.open.error} err · ${a.open.warning} warn` : 'none'} />
        <Stat label="Handled" value={`${a.handled} waiting · ${a.reviewed} reviewed`} />
        <Stat label="Changes" value={a.changes ? String(a.changes) : 'none'} />
      </div>
      {(openEffect || a.changes > 0) && (
        <div className="grid grid-cols-2 gap-2 text-[12px]">
          {openEffect && (
            <Stat label="If the open issues are corrected" value={`Fed ${fmtEffect(a.open_effect.federal)} · CA ${fmtEffect(a.open_effect.california)}`} />
          )}
          {a.changes > 0 && (
            <Stat label="Changes made so far" value={`Fed ${fmtEffect(a.change_effect.federal)} · CA ${fmtEffect(a.change_effect.california)}`} />
          )}
        </div>
      )}
      {a.top_open.length > 0 && (
        <ul className="space-y-0.5 text-[12px]">
          {a.top_open.map((f) => (
            <li key={f.id} className="flex items-baseline gap-1.5">
              <span className={`h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full ${f.severity === 'error' ? 'bg-red-500' : 'bg-amber-400'}`} />
              <Link to={`/findings?id=${f.id}`} className="min-w-0 truncate text-slate-700 hover:text-indigo-700 hover:underline">{f.title}</Link>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-x-3 text-[12px]">
        {AREA_REPORT_FOR[a.key] && (
          <Link to={`/reports?tab=area&r=${AREA_REPORT_FOR[a.key]}`} className="text-indigo-700 hover:underline">Detailed report →</Link>
        )}
        {a.inbox_open > 0 && (
          <Link to={`/inbox?area=${a.key}`} className="text-indigo-700 hover:underline">Open in Inbox →</Link>
        )}
        {Object.entries(a.grouped_open).map(([family, n]) => (
          <Link key={family} to={`/findings?check=${family}&area=${a.key}`} className="text-indigo-700 hover:underline">
            {n} {GROUP_LABEL[family] ?? family} →
          </Link>
        ))}
      </div>
    </div>
  )
}

// checks the Inbox batches into one card; their issues are listed on the Findings page
const GROUP_LABEL: Record<string, string> = { P5: 'prior-year variances', P6: 'unused documents' }

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-2 py-1">
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="num text-slate-800">{value}</div>
    </div>
  )
}

// ------------------------------------------------------------------ reconciliations
function Reconciliations() {
  const { data } = useReport<ReconciliationGroup[]>('reconciliations')
  if (!data) return <div className="text-slate-400">Loading the reconciliations…</div>
  const agree = data.reduce((n, g) => n + g.agree.length, 0)
  const differ = data.reduce((n, g) => n + g.differ.length, 0)
  return (
    <div className="space-y-4">
      <p className="text-slate-600">
        Figures that should agree, checked independently of the engine: <b>{agree}</b> agree, <b>{differ}</b> do not.
        Differences come first.
      </p>
      {data.map((g) => <Group key={g.title} g={g} />)}
    </div>
  )
}

function Group({ g }: { g: ReconciliationGroup }) {
  const [all, setAll] = useState(false)
  const shown = all ? g.agree : g.agree.slice(0, 4)
  return (
    <section className="panel p-3">
      <div className="mb-1 flex flex-wrap items-baseline gap-2">
        <h2 className="font-semibold text-slate-900">{g.title}</h2>
        {g.differ.length > 0 && <span className="chip border-red-200 bg-red-50 text-red-700">{g.differ.length} differ</span>}
        {g.agree.length > 0 && <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">{g.agree.length} agree</span>}
      </div>
      <p className="mb-2 text-[12px] text-slate-500">{g.covers.join('; ')}</p>
      <div className="divide-y divide-slate-100">
        {g.differ.map((d) => (
          <div key={d.finding_id} className="flex flex-wrap items-baseline gap-2 py-1.5 text-[13px]">
            <span className={`chip ${d.severity === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>✗</span>
            <Link to={`/findings?id=${d.finding_id}`} className="min-w-0 flex-1 text-slate-800 hover:text-indigo-700 hover:underline">{d.title}</Link>
            {d.corrections[0] && (
              <span className="num text-[12px] text-slate-500">
                {fmtValue(d.corrections[0].current)} → {fmtValue(d.corrections[0].proposed)}
              </span>
            )}
            {d.state !== 'open' && (
              <span className="chip border-slate-300 bg-slate-100 text-slate-600">{d.state === 'reviewed' ? '✓ reviewed' : 'handled · waiting for review'}</span>
            )}
          </div>
        ))}
        {shown.map((a, i) => (
          <div key={a.check + i} className="flex flex-wrap items-baseline gap-2 py-1.5 text-[13px]">
            <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">✓</span>
            <span className="min-w-0 flex-1 text-slate-700">{a.what}</span>
            {(a.engine !== 0 || a.independent !== 0) && (
              <span className="num text-[12px] text-slate-500" title="engine / independent">
                {fmtValue(a.engine)} = {fmtValue(a.independent)}
              </span>
            )}
            {a.nodes.slice(0, 2).map((n) => <Ref key={n} id={n} />)}
          </div>
        ))}
      </div>
      {g.agree.length > 4 && (
        <button onClick={() => setAll(!all)} className="mt-1 text-[12px] text-indigo-700 hover:underline">
          {all ? 'Show fewer' : `Show all ${g.agree.length} that agree`}
        </button>
      )}
    </section>
  )
}

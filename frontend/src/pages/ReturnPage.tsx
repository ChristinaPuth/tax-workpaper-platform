import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { FindingState, LineRow, Severity, WorkingLine, WorkingReturn } from '../api'
import { FORMS, FORM_NAME, fmtValue } from '../format'
import { TracePanel } from '../components/TracePanel'
import { openFindings, useFindingStates, useLines, useOverview, useWorking } from '../queries'
import { Empty, FlagDots, KindBadge } from '../components/ui'
import { Splitter } from '../components/Splitter'
import { useColumnWidth } from '../useColumnWidth'
import { Tech, Term } from '../components/Help'

// [engine summary jurisdiction, engine summary key, working summary key or working line key, label]
const SUMMARY_FIELDS: [string, string, string, string][] = [
  ['federal', 'agi', 'agi', 'AGI'],
  ['federal', 'taxable_income', 'line:F1040.15', 'Taxable income'],
  ['federal', 'total_tax', 'total_tax', 'Total tax'],
  ['federal', 'balance_due', 'balance_due', 'Federal balance due'],
  ['california', 'total_tax', 'ca_total_tax', 'CA tax'],
  ['california', 'balance_due', 'ca_balance_due', 'CA balance due'],
]

const SUMMARY_TERM: Record<string, string> = {
  AGI: 'AGI', 'Taxable income': 'Taxable income', 'Total tax': 'Total tax', 'Federal balance due': 'Balance due',
  'CA tax': '540NR', 'CA balance due': 'Balance due',
}

function sum(rows: LineRow[], s: Severity, states: Record<string, FindingState> | undefined) {
  return rows.reduce((n, r) => n + (openFindings(r, states).open[s] ?? 0), 0)
}

function workingFor(w: WorkingReturn | undefined, key: string): { value: number | null; changed: boolean; estimated: boolean } | null {
  if (!w) return null
  if (key.startsWith('line:')) {
    const l = w.lines[key.slice(5)]
    return l && typeof l.value === 'number' ? { value: l.value, changed: l.value !== l.engine, estimated: l.partial } : null
  }
  const s = w.summary[key]
  if (!s || s.value === null) return null
  // total tax and balances include the rate estimate; AGI is exact arithmetic unless an input awaits recompute
  return { value: s.value, changed: s.value !== s.engine, estimated: key !== 'agi' || !!w.lines['F1040.11']?.partial }
}

export function ReturnPage() {
  const [params, setParams] = useSearchParams()
  const { data: overview } = useOverview()
  const version = params.get('v') || overview?.latest_version || ''
  const form = params.get('form') || 'F1040'
  const selected = params.get('line')
  const { data: lines = [] } = useLines(version)
  const { data: working } = useWorking(version)
  const { data: states } = useFindingStates()

  const byForm = useMemo(() => {
    const m: Record<string, LineRow[]> = {}
    lines.forEach((l) => (m[l.form] ??= []).push(l))
    return m
  }, [lines])
  const changedByForm = useMemo(() => {
    const m: Record<string, number> = {}
    // only lines whose number actually moved; "needs recompute" alone does not change what you read
    Object.entries(working?.lines ?? {})
      .filter(([, l]) => l.value !== l.engine)
      .forEach(([k]) => (m[k.split('.')[0]] = (m[k.split('.')[0]] ?? 0) + 1))
    return m
  }, [working])

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    Object.entries(patch).forEach(([k, v]) => (v === null ? next.delete(k) : next.set(k, v)))
    setParams(next)
  }
  const summary = overview?.versions.find((v) => v.version === version)
  const formsCol = useColumnWidth('return.forms', 240, 160, 420)
  const traceCol = useColumnWidth('return.trace', 520, 340, 900)
  const hasChanges = !!working && working.adjustments.length > 0

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-6 border-b border-slate-200 bg-white px-4 py-2">
        <div className="flex items-center gap-1">
          {overview?.versions.map((v) => (
            <button
              key={v.version}
              title={v.trigger}
              onClick={() => set({ v: v.version })}
              className={`rounded-md px-2 py-1 text-xs font-medium ${v.version === version ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              {v.version}
            </button>
          ))}
          {hasChanges && <span className="ml-1 chip border-indigo-300 bg-indigo-50 text-indigo-700">+ {working!.adjustments.length} change{working!.adjustments.length > 1 ? 's' : ''}</span>}
        </div>
        {summary &&
          SUMMARY_FIELDS.map(([j, k, wk, label]) => {
            const engine = summary.summary[j]?.[k]
            const w = workingFor(working, wk)
            return (
              <div key={label} className="leading-tight">
                <div className="text-[10px] uppercase tracking-wide text-slate-400"><Term t={SUMMARY_TERM[label]}>{label}</Term></div>
                {w?.changed ? (
                  <div className="flex items-baseline gap-1.5">
                    <span className="num font-semibold text-indigo-800" title={w.estimated ? 'Estimated: change x tax-effect rates' : 'Recomputed'}>
                      {w.estimated ? '≈ ' : ''}
                      {fmtValue(w.value)}
                    </span>
                    <span className="num text-[11px] text-slate-400 line-through">{fmtValue(engine)}</span>
                  </div>
                ) : (
                  <div className="num font-semibold text-slate-800">{fmtValue(engine)}</div>
                )}
              </div>
            )
          })}
      </div>
      {working && working.warnings.length > 0 && (
        <div className="space-y-0.5 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-[12px] text-amber-900">
          {working.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <nav style={{ width: formsCol.width }} className="min-w-[140px] shrink overflow-y-auto bg-white py-1">
          {FORMS.filter(([f]) => byForm[f]).map(([f, name]) => {
            const rows = byForm[f]
            const e = sum(rows, 'error', states)
            const w = sum(rows, 'warning', states)
            return (
              <button
                key={f}
                onClick={() => set({ form: f, line: null })}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left ${f === form ? 'bg-indigo-50 text-indigo-800' : 'hover:bg-slate-50'}`}
              >
                <span className="min-w-0 flex-1 truncate">{name}</span>
                {changedByForm[f] && <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" title="Numbers changed on this form" />}
                {e > 0 && <span className="num rounded bg-red-100 px-1 text-[11px] text-red-700">{e}</span>}
                {w > 0 && <span className="num rounded bg-amber-100 px-1 text-[11px] text-amber-800">{w}</span>}
              </button>
            )
          })}
        </nav>
        <Splitter side="left" width={formsCol.width} onChange={formsCol.setWidth} onReset={formsCol.reset} />

        <section className="min-w-[240px] flex-1 overflow-y-auto">
          <div className="sticky top-0 z-10 flex items-center border-b border-slate-200 bg-slate-50/95 px-4 py-2 backdrop-blur">
            <h1 className="font-semibold text-slate-900">{FORM_NAME[form] ?? form}</h1>
            {hasChanges && (
              <span className="ml-auto flex items-center gap-1 text-[11px] text-slate-500">
                <KindBadge kind="adjusted" /> changed by a person <KindBadge kind="propagated" /> recomputed from it
                <KindBadge kind="stale" /> engine formula, awaiting rerun
              </span>
            )}
          </div>
          <LinesTable
            rows={byForm[form] ?? []}
            working={working?.lines ?? {}}
            states={states}
            selected={selected}
            onSelect={(k) => set({ line: k })}
          />
        </section>

        <Splitter side="right" width={traceCol.width} onChange={traceCol.setWidth} onReset={traceCol.reset} />
        <aside style={{ width: traceCol.width }} className="min-w-[300px] shrink overflow-y-auto bg-slate-50">
          {selected ? (
            <TracePanel version={version} lineKey={selected} />
          ) : (
            <Empty>Select a line to see how it was built and where every number came from.</Empty>
          )}
        </aside>
      </div>
    </div>
  )
}

// Form 8949 boxes: which part a sale is reported in, and what that says about it.
const BOX: Record<string, string> = {
  A: 'Box A · short-term, basis reported to the IRS', B: 'Box B · short-term, basis not reported to the IRS',
  C: 'Box C · short-term, not reported on Form 1099-B', D: 'Box D · long-term, basis reported to the IRS',
  E: 'Box E · long-term, basis not reported to the IRS', F: 'Box F · long-term, not reported on Form 1099-B',
  G: 'Box G · short-term digital assets, basis reported to the IRS', H: 'Box H · short-term digital assets, basis not reported to the IRS',
  I: 'Box I · short-term digital assets, not reported on Form 1099-DA', J: 'Box J · long-term digital assets, basis reported to the IRS',
  K: 'Box K · long-term digital assets, basis not reported to the IRS', L: 'Box L · long-term digital assets, not reported on Form 1099-DA',
}
const whole = (n: number) => Math.round(n).toLocaleString('en-US')
const PAGE = 150

function LinesTable({ rows, working, states, selected, onSelect }: {
  rows: LineRow[]
  working: Record<string, WorkingLine>
  states: Record<string, FindingState> | undefined
  selected: string | null
  onSelect: (k: string) => void
}) {
  // Large detail (hundreds of sales) opens on totals + flagged / changed rows; the rest is searched, grouped
  // by part with subtotals, sorted, and shown a page at a time.
  const isDetail = rows.length > 60
  const [show, setShow] = useState<'flagged' | 'all'>('flagged')
  const [query, setQuery] = useState('')
  const [part, setPart] = useState<string | null>(null)
  const [sort, setSort] = useState<'form' | 'desc' | 'asc'>('form')
  const [limit, setLimit] = useState(PAGE)
  const partOf = (r: LineRow) => (r.line.includes('.') ? r.line.split('.')[0] : null)
  const parts = useMemo(() => {
    if (!isDetail) return []
    const m = new Map<string, { n: number; total: number; flagged: number }>()
    rows.forEach((r) => {
      const p = partOf(r)
      if (!p || r.key.endsWith('total')) return
      const cur = m.get(p) ?? { n: 0, total: 0, flagged: 0 }
      const v = working[r.key]?.value ?? r.value
      m.set(p, { n: cur.n + 1, total: cur.total + (typeof v === 'number' ? v : 0), flagged: cur.flagged + (Object.keys(r.findings).length ? 1 : 0) })
    })
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows, working, isDetail])
  const valueOf = (r: LineRow) => { const v = working[r.key]?.value ?? r.value; return typeof v === 'number' ? v : 0 }
  const filtered = useMemo(() => {
    if (!isDetail) return rows
    const q = query.trim().toLowerCase()
    let out = rows.filter((r) =>
      (show === 'all' || q || part || r.key.endsWith('total') || Object.keys(r.findings).length > 0 || r.key === selected || working[r.key])
      && (!part || partOf(r) === part)
      && (!q || r.label.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)))
    if (sort !== 'form') out = [...out].sort((a, b) => (sort === 'desc' ? valueOf(b) - valueOf(a) : valueOf(a) - valueOf(b)))
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, working, isDetail, show, query, part, sort, selected])
  const visible = filtered.slice(0, limit)
  return (
    <div>
      {isDetail && (
        <div className="space-y-1.5 border-b border-slate-200 bg-white px-4 py-2 text-[12px] text-slate-500">
          <div className="flex flex-wrap items-center gap-2">
            <input value={query} onChange={(e) => { setQuery(e.target.value); setLimit(PAGE) }} placeholder="Search description, security, date…"
              aria-label="Search lines" className="w-56 rounded-md border border-slate-300 px-2 py-1 text-[12px] text-slate-800" />
            <select value={show} onChange={(e) => { setShow(e.target.value as typeof show); setLimit(PAGE) }} aria-label="Which lines"
              className="rounded-md border border-slate-300 px-2 py-1 text-[12px] text-slate-800">
              <option value="flagged">Totals, flagged and changed</option>
              <option value="all">All {rows.length} lines</option>
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort"
              className="rounded-md border border-slate-300 px-2 py-1 text-[12px] text-slate-800">
              <option value="form">Form order</option>
              <option value="desc">Largest amount first</option>
              <option value="asc">Smallest amount first</option>
            </select>
            <span className="ml-auto">{filtered.length} of {rows.length} lines</span>
          </div>
          {parts.length > 1 && (
            <div className="flex flex-wrap gap-1">
              <button onClick={() => setPart(null)} className={`chip ${part === null ? 'border-indigo-400 bg-indigo-50 text-indigo-800' : 'border-slate-200'}`}>All parts</button>
              {parts.map(([p, v]) => (
                <button key={p} onClick={() => { setPart(part === p ? null : p); setLimit(PAGE) }} title={BOX[p] ?? `Part ${p}`}
                  className={`chip ${part === p ? 'border-indigo-400 bg-indigo-50 text-indigo-800' : 'border-slate-200'}`}>
                  {BOX[p]?.split(' · ')[0] ?? p} · {v.n} · <span className="num">{whole(v.total)}</span>
                  {v.flagged > 0 && <span className="text-amber-700"> · {v.flagged} flagged</span>}
                </button>
              ))}
            </div>
          )}
          {part && BOX[part] && <div className="text-slate-600">{BOX[part]}: {parts.find(([p]) => p === part)?.[1].n} sales, net <b className="num">{whole(parts.find(([p]) => p === part)?.[1].total ?? 0)}</b></div>}
        </div>
      )}
      <table className="w-full">
        <tbody>
          {visible.map((r) => {
            const w = working[r.key]
            const moved = w && w.value !== w.engine
            const { open, addressed } = openFindings(r, states)
            return (
              <tr
                key={r.key}
                onClick={() => onSelect(r.key)}
                className={`cursor-pointer border-b border-slate-100 ${r.key === selected ? 'bg-indigo-50' : 'bg-white hover:bg-slate-50'}`}
              >
                <Tech><td className="w-28 px-4 py-1.5 font-mono text-[11px] text-slate-400">{r.key}</td></Tech>
                <td className="py-1.5 pr-2">
                  {r.label}
                  {r.jurisdiction === 'california' && <span className="chip ml-1 border-slate-200 text-slate-500">CA</span>}
                </td>
                <td className="w-px whitespace-nowrap pr-2">
                  <span className="inline-flex gap-1">
                    {w && <KindBadge kind={w.kind} partial={w.partial} />}
                    <FlagDots findings={open} />
                    {addressed > 0 && (
                      <span className="chip border-slate-300 bg-slate-100 text-slate-600" title="Issues on this line already addressed by a change">
                        ✓ {addressed} addressed
                      </span>
                    )}
                  </span>
                </td>
                <td className="w-36 px-4 py-1.5 text-right">
                  <div className={`num font-medium ${moved ? 'text-indigo-800' : ''}`}>{fmtValue(w ? w.value : r.value)}</div>
                  {moved && <div className="num text-[11px] text-slate-400 line-through">{fmtValue(w.engine)}</div>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {filtered.length > limit && (
        <div className="flex justify-center p-3">
          <button className="btn" onClick={() => setLimit(limit + PAGE)}>Show {Math.min(PAGE, filtered.length - limit)} more of {filtered.length - limit}</button>
        </div>
      )}
    </div>
  )
}

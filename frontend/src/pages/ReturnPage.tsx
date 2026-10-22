import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type LineRow, type Severity } from '../api'
import { FORMS, FORM_NAME, fmtValue } from '../format'
import { TracePanel } from '../components/TracePanel'
import { useLines } from '../queries'
import { Empty, FlagDots } from '../components/ui'

interface Overview {
  versions: { version: string; computed_at: string; trigger: string; summary: Record<string, Record<string, number>> }[]
  latest_version: string
}

const SUMMARY_FIELDS: [string, string, string][] = [
  ['federal', 'agi', 'AGI'],
  ['federal', 'taxable_income', 'Taxable income'],
  ['federal', 'total_tax', 'Total tax'],
  ['federal', 'balance_due', 'Federal balance due'],
  ['california', 'total_tax', 'CA tax'],
  ['california', 'balance_due', 'CA balance due'],
]

function sum(rows: LineRow[], s: Severity) {
  return rows.reduce((n, r) => n + (r.findings[s] ?? 0), 0)
}

export function ReturnPage() {
  const [params, setParams] = useSearchParams()
  const { data: overview } = useQuery({ queryKey: ['overview'], queryFn: () => api<Overview>('/overview') })
  const version = params.get('v') || overview?.latest_version || 'v3'
  const form = params.get('form') || 'F1040'
  const selected = params.get('line')
  const { data: lines = [] } = useLines(version)

  const byForm = useMemo(() => {
    const m: Record<string, LineRow[]> = {}
    lines.forEach((l) => (m[l.form] ??= []).push(l))
    return m
  }, [lines])

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    Object.entries(patch).forEach(([k, v]) => (v === null ? next.delete(k) : next.set(k, v)))
    setParams(next)
  }
  const summary = overview?.versions.find((v) => v.version === version)

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
        </div>
        {summary &&
          SUMMARY_FIELDS.map(([j, k, label]) => (
            <div key={label} className="leading-tight">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
              <div className="num font-semibold text-slate-800">{fmtValue(summary.summary[j]?.[k])}</div>
            </div>
          ))}
      </div>

      <div className="flex min-h-0 flex-1">
        <nav className="w-60 shrink-0 overflow-y-auto border-r border-slate-200 bg-white py-1">
          {FORMS.filter(([f]) => byForm[f]).map(([f, name]) => {
            const rows = byForm[f]
            const e = sum(rows, 'error')
            const w = sum(rows, 'warning')
            return (
              <button
                key={f}
                onClick={() => set({ form: f, line: null })}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left ${f === form ? 'bg-indigo-50 text-indigo-800' : 'hover:bg-slate-50'}`}
              >
                <span className="min-w-0 flex-1 truncate">{name}</span>
                {e > 0 && <span className="num rounded bg-red-100 px-1 text-[11px] text-red-700">{e}</span>}
                {w > 0 && <span className="num rounded bg-amber-100 px-1 text-[11px] text-amber-800">{w}</span>}
              </button>
            )
          })}
        </nav>

        <section className="min-w-0 flex-1 overflow-y-auto">
          <div className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50/95 px-4 py-2 backdrop-blur">
            <h1 className="font-semibold text-slate-900">{FORM_NAME[form] ?? form}</h1>
          </div>
          <LinesTable rows={byForm[form] ?? []} selected={selected} onSelect={(k) => set({ line: k })} />
        </section>

        <aside className="w-[520px] shrink-0 overflow-y-auto border-l border-slate-200 bg-slate-50">
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

function LinesTable({ rows, selected, onSelect }: { rows: LineRow[]; selected: string | null; onSelect: (k: string) => void }) {
  const [showAll, setShowAll] = useState(false)
  // Large detail (hundreds of sales) collapses to totals + flagged rows until asked for.
  const isDetail = rows.length > 60
  const visible = isDetail && !showAll
    ? rows.filter((r) => r.key.endsWith('total') || Object.keys(r.findings).length > 0 || r.key === selected)
    : rows
  return (
    <div>
      {isDetail && (
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-1.5 text-[12px] text-slate-500">
          <span>
            {showAll ? `All ${rows.length} lines` : `Totals and flagged lines (${visible.length} of ${rows.length})`}
          </span>
          <button className="btn" onClick={() => setShowAll(!showAll)}>
            {showAll ? 'Show totals and flagged only' : `Show all ${rows.length}`}
          </button>
        </div>
      )}
      <table className="w-full">
        <tbody>
          {visible.map((r) => (
            <tr
              key={r.key}
              onClick={() => onSelect(r.key)}
              className={`cursor-pointer border-b border-slate-100 ${r.key === selected ? 'bg-indigo-50' : 'bg-white hover:bg-slate-50'}`}
            >
              <td className="w-28 px-4 py-1.5 font-mono text-[11px] text-slate-400">{r.key}</td>
              <td className="py-1.5 pr-2">
                {r.label}
                {r.jurisdiction === 'california' && <span className="chip ml-1 border-slate-200 text-slate-500">CA</span>}
              </td>
              <td className="w-px whitespace-nowrap pr-2">
                <FlagDots findings={r.findings} />
              </td>
              <td className="num w-32 px-4 py-1.5 text-right font-medium">{fmtValue(r.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

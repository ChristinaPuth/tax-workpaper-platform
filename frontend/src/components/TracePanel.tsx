// How a number was built: the line, its rule, its inputs (recursively) and its sources, down to the
// highlighted field on the source page - and, the other way, every line that depends on it.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type LineDetail, type LineRow, type Source, type TraceNode } from '../api'
import { openFindings, useFindingStates, useLatestVersion, useLines, useWorking } from '../queries'
import { ActivityPanel } from './ActivityPanel'
import { RelatedSection } from './Related'
import { AdjustPanel } from './AdjustPanel'
import { fmtValue, formOf } from '../format'
import { Ref } from './Ref'
import { SourcePreview } from './SourcePreview'
import { FindingCard, FlagDots, KindBadge } from './ui'
import { Tech } from './Help'

export function TracePanel({ version, lineKey }: { version: string; lineKey: string }) {
  const { data: detail } = useQuery({ queryKey: ['line', lineKey], queryFn: () => api<LineDetail>(`/lines/${lineKey}`) })
  const { data: trace } = useQuery({
    queryKey: ['trace', version, lineKey],
    queryFn: () => api<TraceNode>(`/trace/${version}/${lineKey}`),
  })
  const { data: impact } = useQuery({
    queryKey: ['impact', version, lineKey],
    queryFn: () => api<{ lines_fed: Downstream[] }>(
      `/impact/${encodeURIComponent(`line:${version}:${lineKey}`)}?version=${version}`),
  })
  const { data: lines = [] } = useLines(version)
  const { data: working } = useWorking(version)
  const latest = useLatestVersion()
  const byKey = Object.fromEntries(lines.map((l) => [l.key, l]))

  if (!detail || !trace) return <div className="p-4 text-slate-400">Loading {lineKey}…</div>
  const versions = Object.keys(detail.by_version)
  const downstream = (impact?.lines_fed ?? []).filter((l) => l.key !== lineKey)
  const w = working?.lines[lineKey]
  const moved = !!w && w.value !== w.engine
  const proposals = detail.findings.flatMap((f) =>
    f.corrections
      .filter((c) => c.line === lineKey && typeof c.proposed === 'number')
      .map((c) => ({ value: c.proposed as number, label: `${f.id}: ${f.title}` })),
  )

  return (
    <div className="space-y-4 p-4">
      <header>
        <div className="font-mono text-[11px] text-slate-400">
          {detail.form} line {detail.line}<Tech> · {lineKey}</Tech>
        </div>
        <h2 className="text-base font-semibold text-slate-900">{detail.label}</h2>
        <div className="mt-1 flex items-baseline gap-3">
          <span className={`num text-2xl font-semibold ${moved ? 'text-indigo-800' : 'text-slate-900'}`}>
            {w?.partial ? '≈ ' : ''}
            {fmtValue(w ? w.value : trace.value)}
          </span>
          {w ? <KindBadge kind={w.kind} partial={w.partial} /> : <span className="chip border-slate-200 bg-slate-50 text-slate-500">engine {version}</span>}
          {moved && <span className="num text-[12px] text-slate-400">engine {version}: <span className="line-through">{fmtValue(trace.value)}</span></span>}
        </div>
        {versions.length > 1 && (
          <div className="mt-2 flex gap-3 text-[12px] text-slate-500">
            {versions.map((v) => (
              <span key={v}>
                {v}: <b className="num text-slate-700">{fmtValue(detail.by_version[v].value)}</b>
              </span>
            ))}
          </div>
        )}
      </header>

      <AdjustPanel
        version={version}
        editable={!!working}
        lineKey={lineKey}
        engineValue={trace.value}
        working={w}
        adjustment={working?.adjustments.find((a) => a.key === lineKey)}
        proposals={proposals}
      />

      {working && <ActivityPanel target={`line:${version}:${lineKey}`} />}

      {/* issues are found on the current version; an older version only points there, so its own numbers
          are not shown next to issues that quote the current ones */}
      {detail.findings.length > 0 && latest && version !== latest && (
        <Link to={`/return?v=${latest}&form=${formOf(lineKey)}&line=${lineKey}`}
          className="block rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-slate-600 hover:border-indigo-300">
          {detail.findings.length} issue{detail.findings.length > 1 ? 's' : ''} on this line in the current version ({latest})
          <span className="ml-1 text-indigo-700">Open in {latest} →</span>
        </Link>
      )}
      {detail.findings.length > 0 && version === latest && (
        <section className="space-y-1.5">
          <div className="section-title">Issues on this line</div>
          {detail.findings.map((f) => (
            <FindingCard key={f.id} f={f} />
          ))}
        </section>
      )}

      <section>
        <div className="section-title mb-1">Rule</div>
        <div className="rounded-md border border-slate-200 bg-white p-2">
          <Tech><span className="font-mono text-[11px] text-slate-500">{detail.rule}</span></Tech>
          {detail.rule_text && <p className="text-slate-700">{detail.rule_text}</p>}
          {detail.note && <p className="mt-1 text-slate-500">Engine note: {detail.note}</p>}
        </div>
      </section>

      <section>
        <div className="section-title mb-1">How it was built</div>
        <div className="rounded-md border border-slate-200 bg-white p-1.5">
          <TraceBody node={trace} byKey={byKey} depth={0} />
        </div>
      </section>

      {downstream.length > 0 && <Feeds version={version} lines={downstream} />}

      {version === latest && <RelatedSection node={`line:${version}:${lineKey}`} />}
    </div>
  )
}

interface Downstream {
  key: string
  label: string
  value: number | string | null
  distance: number
}

// Where this number goes: the lines computed directly from it, then everything further down on request.
function Feeds({ version, lines }: { version: string; lines: Downstream[] }) {
  const [open, setOpen] = useState(false)
  const direct = lines.filter((l) => l.distance === 1)
  const further = lines.filter((l) => l.distance > 1)
  return (
    <section>
      <div className="section-title mb-1">
        Feeds {lines.length} line{lines.length > 1 ? 's' : ''}
      </div>
      <div className="rounded-md border border-slate-200 bg-white p-1.5">
        <div className="px-1 pb-0.5 text-[11px] text-slate-400">Directly</div>
        {direct.map((l) => (
          <Link
            key={l.key}
            to={`/return?v=${version}&form=${formOf(l.key)}&line=${l.key}`}
            className="flex items-center gap-1.5 rounded px-1 py-0.5 hover:bg-slate-50 hover:text-indigo-700"
          >
            <Tech><span className="font-mono text-[11px] text-slate-400">{l.key}</span></Tech>
            <span className="min-w-0 flex-1 truncate">{l.label}</span>
            <span className="num w-24 text-right">{fmtValue(l.value)}</span>
          </Link>
        ))}
        {further.length > 0 && (
          <div className="mt-1 border-t border-slate-100 px-1 pt-1">
            <button onClick={() => setOpen(!open)} className="text-[12px] text-indigo-700 hover:underline">
              {open ? 'Hide' : 'Show'} {further.length} more further down
            </button>
            {open && (
              <div className="mt-1 flex flex-wrap gap-1">
                {further.map((l) => (
                  <Ref key={l.key} id={`line:${version}:${l.key}`} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

function TraceBody({ node, byKey, depth }: { node: TraceNode; byKey: Record<string, LineRow>; depth: number }) {
  return (
    <div className="space-y-0.5">
      {node.sources.map((s) => (
        <SourceRow key={s.id} s={s} />
      ))}
      {node.inputs.map((n) => (
        <InputRow key={n.id} node={n} byKey={byKey} depth={depth + 1} />
      ))}
      {node.sources.length === 0 && node.inputs.length === 0 && (
        <div className="px-2 py-1 text-[12px] text-slate-400">No inputs or sources cited by the engine.</div>
      )}
    </div>
  )
}

function InputRow({ node, byKey, depth }: { node: TraceNode; byKey: Record<string, LineRow>; depth: number }) {
  const [open, setOpen] = useState(depth < 2)
  const { data: states } = useFindingStates()
  const key = node.id.split(':').slice(2).join(':')
  const row = byKey[key]
  const version = node.id.split(':')[1]
  const leaf = node.inputs.length === 0 && node.sources.length === 0
  return (
    <div>
      <div className="flex items-center gap-1.5 rounded px-1 py-0.5 hover:bg-slate-50">
        <button
          onClick={() => setOpen(!open)}
          disabled={leaf}
          className="w-4 text-slate-400 disabled:opacity-0"
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          {open ? '▾' : '▸'}
        </button>
        <Link
          to={`/return?v=${version}&form=${formOf(key)}&line=${key}`}
          className="min-w-0 flex-1 truncate hover:text-indigo-700"
          title={row?.label}
        >
          <Tech><span className="font-mono text-[11px] text-slate-400">{key}</span></Tech> {row?.label}
        </Link>
        {row && <FlagDots findings={openFindings(row, states).open} />}
        <span className="num w-24 text-right font-medium">{fmtValue(node.value)}</span>
      </div>
      {open && !leaf && (
        <div className="ml-3 border-l border-slate-200 pl-2">
          <TraceBody node={node} byKey={byKey} depth={depth} />
        </div>
      )}
    </div>
  )
}

function SourceRow({ s }: { s: Source }) {
  const [open, setOpen] = useState(false)
  if (s.kind !== 'extracted_value') {
    return (
      <div className="flex items-center gap-1.5 px-1 py-0.5 text-[12px]">
        <span className="w-4" />
        <span className="text-slate-400">source</span> <Ref id={s.id} />
      </div>
    )
  }
  const ev = s.id.slice(3)
  const lowConf = (s.confidence ?? 1) < 0.8
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-indigo-50 ${open ? 'bg-indigo-50' : ''}`}
      >
        <span className="w-4 text-indigo-400">{open ? '▾' : '▸'}</span>
        <span className="chip border-indigo-200 bg-white font-mono text-indigo-700">
          {s.document} p{s.page}
        </span>
        <span className="min-w-0 flex-1 truncate text-slate-600">{s.field}</span>
        {lowConf && <span className="chip border-red-200 bg-red-50 text-red-700">conf {s.confidence}</span>}
        <span className="num w-24 text-right">{fmtValue(s.value)}</span>
      </button>
      {open && s.document && s.page && <SourcePreview doc={s.document} page={s.page} evId={ev} />}
    </div>
  )
}

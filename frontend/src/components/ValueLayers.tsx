// The three layers of one extracted value side by side: printed on the page, read by the pipeline,
// used by the return. Confident mistakes live where these disagree.
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type ValueLayers as VL } from '../api'
import { fmtValue, formOf } from '../format'
import { FindingCard } from './ui'
import { isMasked, RevealButton, useReveal } from './Reveal'

function numeric(v: unknown): number | null {
  return typeof v === 'number' ? v : null
}

export function ValueLayers({ evId }: { evId: string }) {
  const { data: v } = useQuery({ queryKey: ['value', evId], queryFn: () => api<VL>(`/values/${evId}`) })
  const shown = useReveal(`ev:${evId}`)
  if (!v) return <div className="h-24 animate-pulse rounded-md bg-slate-100" />
  const masked = isMasked(v.extracted.text_as_read) || isMasked(v.printed.text)
  const unmasked = shown.content ? String(shown.content.text_as_read ?? '') : null

  const printedOk = v.printed.found
  const lowConf = v.extracted.confidence < 0.8
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="font-medium text-slate-800">{v.label}</div>
          <div className="font-mono text-[11px] text-slate-400">
            {v.id} · {v.document} p{v.page} · {v.field}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5 text-[12px]">
        <Layer title="On the page" bad={!printedOk}>
          {printedOk ? (
            <span className="font-mono">{unmasked && isMasked(v.printed.text) ? unmasked : v.printed.text}</span>
          ) : (
            <span className="text-red-700">Not printed on this page</span>
          )}
        </Layer>
        <Layer title="Pipeline read" bad={!printedOk || lowConf}>
          <span className="font-mono">{unmasked ?? (v.extracted.text_as_read || '(blank)')}</span>
          <span className={`block text-[11px] ${lowConf ? 'text-red-700' : 'text-slate-400'}`}>
            confidence {v.extracted.confidence}
          </span>
        </Layer>
        <Layer title={`Used in return (${v.version})`}>
          {v.used.length === 0 ? (
            <span className="text-slate-400">Not used by any line</span>
          ) : (
            v.used.map((u) => {
              const differs = u.sources === 1 && numeric(u.value) !== null && numeric(v.extracted.value) !== null
                && Math.round(numeric(u.value)!) !== Math.round(numeric(v.extracted.value)!)
              return (
                <Link
                  key={u.key}
                  to={`/return?v=${v.version}&form=${formOf(u.key)}&line=${u.key}`}
                  className="block hover:text-indigo-700"
                >
                  <span className="font-mono">{u.key}</span>{' '}
                  <span className={`num ${differs ? 'text-amber-700' : ''}`}>{fmtValue(u.value)}</span>
                  {u.sources > 1 && <span className="text-[11px] text-slate-400"> · 1 of {u.sources} sources</span>}
                </Link>
              )
            })
          )}
        </Layer>
      </div>
      {masked && <RevealButton r={shown} />}
      {v.printed.context && (
        <p className="rounded bg-slate-50 px-2 py-1 font-mono text-[11px] text-slate-500">…{v.printed.context}…</p>
      )}
      {v.findings.map((f) => (
        <FindingCard key={f.id} f={f} />
      ))}
    </div>
  )
}

function Layer({ title, bad = false, children }: { title: string; bad?: boolean; children: React.ReactNode }) {
  return (
    <div className={`rounded-md border p-2 ${bad ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-white'}`}>
      <div className="section-title mb-1">{title}</div>
      {children}
    </div>
  )
}

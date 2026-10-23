import type { ReactNode } from 'react'
import type { Finding, FindingState, Severity } from '../api'
import { fmtEffect, fmtTime } from '../format'
import { useFindingStates } from '../queries'
import { useSession } from '../session-context'
import { Ref } from './Ref'

const SEV: Record<Severity, string> = {
  error: 'border-red-200 bg-red-50 text-red-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  info: 'border-sky-200 bg-sky-50 text-sky-700',
}

export function SeverityChip({ severity, count }: { severity: Severity; count?: number }) {
  return (
    <span className={`chip ${SEV[severity]}`}>
      {count !== undefined && <b className="num">{count}</b>}
      {severity}
    </span>
  )
}

export function FlagDots({ findings }: { findings: Partial<Record<Severity, number>> }) {
  const order: Severity[] = ['error', 'warning', 'info']
  return (
    <span className="inline-flex gap-1">
      {order.filter((s) => findings[s]).map((s) => (
        <SeverityChip key={s} severity={s} count={findings[s]} />
      ))}
    </span>
  )
}

const STATUS: Record<string, string> = {
  used: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  superseded: 'border-slate-300 bg-slate-100 text-slate-600',
  not_extracted: 'border-slate-300 bg-slate-100 text-slate-600',
  explained_in_note: 'border-sky-200 bg-sky-50 text-sky-700',
  used_without_line_link: 'border-amber-200 bg-amber-50 text-amber-800',
  unused: 'border-amber-200 bg-amber-50 text-amber-800',
}

export function StatusChip({ status }: { status: string }) {
  return <span className={`chip ${STATUS[status] ?? 'border-slate-200 bg-slate-50'}`}>{status.replace(/_/g, ' ')}</span>
}

// Whether an issue has been dealt with, in the same words everywhere it appears.
export function StateChip({ state }: { state: FindingState | undefined }) {
  const { people } = useSession()
  if (!state || state.state === 'open') return null
  const who = people.find((p) => p.id === state.by)?.name ?? state.by
  return state.state === 'reviewed' ? (
    <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">✓ reviewed</span>
  ) : (
    <span className="chip border-slate-300 bg-slate-100 text-slate-600" title={`${who} changed ${state.line}${state.at ? ` on ${fmtTime(state.at)}` : ''}`}>
      addressed · waiting for review
    </span>
  )
}

export function FindingCard({ f, compact = false }: { f: Finding; compact?: boolean }) {
  const { data: states } = useFindingStates()
  const { people } = useSession()
  const st = states?.[f.id]
  const handled = !!st && st.state !== 'open'
  const tone = handled ? 'border-slate-200 bg-slate-50' : f.severity === 'error' ? 'border-red-200 bg-red-50/40' : 'border-slate-200 bg-white'
  return (
    <div className={`rounded-md border p-2.5 ${tone}`}>
      <div className="flex items-start gap-2">
        {handled ? <StateChip state={st} /> : <SeverityChip severity={f.severity} />}
        <div className="min-w-0 flex-1">
          <div className={`font-medium ${handled ? 'text-slate-500' : 'text-slate-800'}`}>{f.title}</div>
          {handled && (
            <p className="mt-0.5 text-[12px] text-slate-500">
              {people.find((p) => p.id === st!.by)?.name ?? st!.by} changed {st!.line}
              {st!.at ? ` on ${fmtTime(st!.at)}` : ''}.{' '}
              {st!.state === 'adjusted' ? 'Waiting for a reviewer to sign off.' : 'Signed off.'}
            </p>
          )}
          {!compact && <p className="mt-1 text-slate-600">{f.detail}</p>}
          {(f.federal_effect || f.california_effect) ? (
            <div className="mt-1 text-[11px] text-slate-500">
              Estimated effect — federal <b className="num text-slate-700">{fmtEffect(f.federal_effect)}</b>, California{' '}
              <b className="num text-slate-700">{fmtEffect(f.california_effect)}</b>
            </div>
          ) : null}
          {!compact && f.corrections.length > 0 && (
            <ul className="mt-1.5 space-y-0.5 text-[12px]">
              {f.corrections.map((c, i) => (
                <li key={i} className="font-mono text-slate-600">
                  {c.line}: <span className="line-through">{String(c.current)}</span> → <b>{String(c.proposed)}</b>
                </li>
              ))}
            </ul>
          )}
          {!compact && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {[...f.nodes, ...f.evidence].map((n) => (
                <Ref key={n} id={n} />
              ))}
            </div>
          )}
        </div>
        <span className="font-mono text-[11px] text-slate-400">{f.id}</span>
      </div>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="p-6 text-center text-slate-400">{children}</div>
}

// Where a number comes from (NF-02): every working value says whether it can be trusted as is.
const KIND: Record<string, { label: string; cls: string; title: string }> = {
  adjusted: { label: 'adjusted', cls: 'border-indigo-300 bg-indigo-50 text-indigo-700', title: 'Changed by a person; the engine value is kept' },
  propagated: { label: 'updated', cls: 'border-sky-300 bg-sky-50 text-sky-700', title: 'Recomputed from changed inputs with the engine’s own arithmetic' },
  stale: { label: 'needs recompute', cls: 'border-amber-300 bg-amber-50 text-amber-800', title: 'Depends on a change but is an engine formula; showing the engine value until it reruns' },
}

export function KindBadge({ kind, partial = false }: { kind: string; partial?: boolean }) {
  const k = KIND[kind]
  if (!k) return null
  return (
    <span className={`chip ${k.cls}`} title={partial ? `${k.title}. Some inputs still need a recompute.` : k.title}>
      {partial ? '≈ ' : ''}
      {k.label}
    </span>
  )
}

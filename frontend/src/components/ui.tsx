import { useState, type ReactNode } from 'react'
import { api, JUDGMENT_KINDS, type Finding, type FindingState, type Severity } from '../api'
import { fmtEffect, fmtTime, fmtValue } from '../format'
import { useFindingStates, useLatestVersion, usePostBatch, useView } from '../queries'
import { useQuery } from '@tanstack/react-query'
import { useSession } from '../session-context'
import { Ref } from './Ref'
import { Tech, Term } from './Help'

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

export function FindingCard({ f, compact = false, selected, onSelect }: {
  f: Finding
  compact?: boolean
  selected?: boolean // shown with a checkbox when the list supports one decision for many
  onSelect?: (checked: boolean) => void
}) {
  const { data: states } = useFindingStates()
  const { people, person } = useSession()
  const [deciding, setDeciding] = useState(false)
  const st = states?.[f.id]
  const handled = !!st && st.state !== 'open'
  const tone = handled ? 'border-slate-200 bg-slate-50' : f.severity === 'error' ? 'border-red-200 bg-red-50/40' : 'border-slate-200 bg-white'
  return (
    <div className={`rounded-md border p-2.5 ${tone}`}>
      <div className="flex items-start gap-2">
        {onSelect && !handled && (
          <input type="checkbox" className="mt-1" checked={!!selected} onChange={(e) => onSelect(e.target.checked)} aria-label={`Select ${f.id}`} />
        )}
        {handled ? <StateChip state={st} /> : <SeverityChip severity={f.severity} />}
        <div className="min-w-0 flex-1">
          <div className={`font-medium ${handled ? 'text-slate-500' : 'text-slate-800'}`}>{f.title}</div>
          {handled && (
            <p className="mt-0.5 text-[12px] text-slate-500">
              {people.find((p) => p.id === st!.by)?.name ?? st!.by}{' '}
              {st!.decision ? `decided: ${st!.decision} (authority: ${st!.authority})` : `changed ${st!.line}`}
              {st!.at ? ` on ${fmtTime(st!.at)}` : ''}.{' '}
              {st!.state === 'reviewed' ? 'Signed off.' : 'Waiting for a reviewer to sign off.'}
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
              {f.corrections.map((c, i) => <CorrectionLine key={i} line={c.line} current={c.current} proposed={c.proposed} />)}
            </ul>
          )}
          {!compact && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {[...f.nodes, ...f.evidence].map((n) => (
                <Ref key={n} id={n} />
              ))}
            </div>
          )}
          {!handled && person?.can.includes('judgment') && !compact && (
            deciding ? (
              <DecisionForm findings={[f]} onDone={() => setDeciding(false)} />
            ) : (
              <button className="btn mt-1.5" onClick={() => setDeciding(true)}>
                Record decision
              </button>
            )
          )}
        </div>
        <Tech><span className="font-mono text-[11px] text-slate-400">{f.id}</span></Tech>
      </div>
    </div>
  )
}

// A proposed correction: the line by name in the simple view, by key in the expert view.
function CorrectionLine({ line, current, proposed }: { line: string; current: unknown; proposed: unknown }) {
  const { simple } = useView()
  const version = useLatestVersion()
  const { data: plain } = useQuery({ queryKey: ['labels'], queryFn: () => api<Record<string, string>>('/labels'), enabled: simple, staleTime: Infinity })
  const name = simple ? plain?.[`line:${version}:${line}`] ?? line : line
  return (
    <li className={simple ? 'text-slate-600' : 'font-mono text-slate-600'}>
      {name}: <span className="line-through">{fmtValue(current)}</span> → <b>{fmtValue(proposed)}</b>
    </li>
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

const KIND_TERM: Record<string, string> = { adjusted: 'Adjusted', propagated: 'Propagated', stale: 'Needs recompute' }

export function KindBadge({ kind, partial = false }: { kind: string; partial?: boolean }) {
  const k = KIND[kind]
  if (!k) return null
  return (
    <span className={`chip ${k.cls}`} title={partial ? `${k.title}. Some inputs still need a recompute.` : k.title}>
      {partial ? '≈ ' : ''}
      <Term t={KIND_TERM[kind]}>{k.label}</Term>
    </span>
  )
}

// Settle one or many findings with a decision. The firm rule: every judgment records its authority.
export function DecisionForm({ findings, onDone }: { findings: Finding[]; onDone: () => void }) {
  const post = usePostBatch()
  const [kind, setKind] = useState<string>(findings.every((f) => f.check.startsWith('P5')) ? 'explanation' : 'judgment')
  const [decision, setDecision] = useState('')
  const [authority, setAuthority] = useState('')
  const valid = decision.trim() && authority.trim() && findings.length > 0
  return (
    <form
      className="mt-1.5 space-y-1.5 rounded-md border border-indigo-200 bg-white p-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (!valid) return
        post.mutate(
          findings.map((f) => ({
            type: 'judgment',
            target: f.nodes[0],
            payload: { kind, decision: decision.trim(), authority: authority.trim(), finding_id: f.id },
          })),
          { onSuccess: onDone },
        )
      }}
    >
      <div className="section-title">
        Decision{findings.length > 1 ? ` for ${findings.length} issues` : ''}
      </div>
      <select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]">
        {JUDGMENT_KINDS.map((k) => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}
      </select>
      <textarea value={decision} onChange={(e) => setDecision(e.target.value)} rows={2} placeholder="What you decided and why"
        className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
      <input value={authority} onChange={(e) => setAuthority(e.target.value)} placeholder="Authority relied on (required): rule, document, client confirmation…"
        className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
      {post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={!valid || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">
          Record decision
        </button>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

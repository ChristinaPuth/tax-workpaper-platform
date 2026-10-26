import { useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import type { InboxItem } from '../api'
import { fmtEffect } from '../format'
import { useInbox } from '../queries'
import { hrefFor } from '../refs'
import { useSession } from '../session-context'
import { Empty, SeverityChip } from '../components/ui'
import { AnswerBox } from '../components/ActivityPanel'
import { WorkPlan } from '../components/WorkPlan'
import { usePostBatch } from '../queries'
import { useMarkVisited, useView } from '../queries'

// "My work": what this person should do next, worst first, in plain language.
const ACROSS = '__across'

export function InboxPage() {
  useMarkVisited('inbox')
  const { person } = useSession()
  const { data } = useInbox()
  const [params] = useSearchParams()
  const [area, setArea] = useState<string | null>(params.get('area'))  // a link from a report opens one area

  // counted like the header (only what needs you), so the chips add up to the total; items that span areas
  // (batches, sign-offs given together, the whole return) get a chip of their own
  const areas = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>()
    data?.sections.filter((s) => s.needs_you).forEach((s) =>
      s.items.forEach((i) => {
        const key = i.area ?? ACROSS
        const cur = m.get(key) ?? { label: i.area ? (i.area_label ?? i.area) : 'Across areas', n: 0 }
        m.set(key, { ...cur, n: cur.n + 1 })
      }),
    )
    return [...m.entries()].sort((a, b) => (a[0] === ACROSS ? 1 : b[0] === ACROSS ? -1 : b[1].n - a[1].n))
  }, [data])

  if (person?.role === 'client') return <Navigate to="/portal" replace /> // clients have their own view
  if (!data) return <div className="p-6 text-slate-400">Loading your work…</div>
  const firstName = person?.name.split(' ')[0] ?? ''

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl p-6">
        <header className="mb-4">
          <h1 className="text-lg font-semibold text-slate-900">
            {data.total === 0 ? `You're all caught up, ${firstName}.` : `${firstName}, ${data.total} thing${data.total > 1 ? 's' : ''} need your attention`}
          </h1>
          <p className="text-slate-500">
            Okafor-Lindqvist · 2025 return{data.total > 0 ? ' · worst first, each with what to do next.' : ''}
          </p>
        </header>
        <WorkPlan />

        {areas.length > 1 && (
          <div className="mb-4 flex flex-wrap gap-1">
            <button onClick={() => setArea(null)} className={pill(area === null)}>
              All areas
            </button>
            {areas.map(([k, v]) => (
              <button key={k} onClick={() => setArea(k)} className={pill(area === k)}>
                {v.label} <span className="num opacity-60">{v.n}</span>
              </button>
            ))}
          </div>
        )}

        {data.total === 0 && <Empty>{data.empty_message}</Empty>}

        {data.sections.map((s) => {
          const items = s.items.filter((i) => !area || (i.area ?? ACROSS) === area)
          if (!items.length) return null
          return (
            <section key={s.key} className="mb-6">
              <div className="mb-2 flex items-baseline gap-2">
                <h2 className={`font-semibold ${s.needs_you ? 'text-slate-800' : 'text-slate-500'}`}>{s.title}</h2>
                <span className="num text-slate-400">{items.length}</span>
                {!s.needs_you && <span className="chip border-slate-200 text-slate-400">not counted</span>}
                {s.hint && <span className="text-[12px] text-slate-400">{s.hint}</span>}
              </div>
              <div className="space-y-2">
                {items.map((i) => (
                  <InboxCard key={i.id} item={i} />
                ))}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}

function pill(active: boolean) {
  return `rounded-full border px-2.5 py-0.5 text-xs ${active ? 'border-slate-800 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`
}

function hrefOf(i: InboxItem): string | null {
  if ((i.kind === 'group' || i.kind === 'decision_batch') && i.check) return `/findings?check=${i.check}`
  if (i.kind === 'return' || i.target?.startsWith('ver:')) return '/filing'
  const href = i.target ? hrefFor(i.target) : null
  return href ?? (i.finding_id ? `/findings?id=${i.finding_id}` : null)
}

function InboxCard({ item: i }: { item: InboxItem }) {
  const [open, setOpen] = useState(false)
  const { simple } = useView()
  const href = hrefOf(i)
  const hasEffect = !!(i.effect.federal || i.effect.california)
  const handled = i.state === 'adjusted' || i.state === 'reviewed'
  const edge = handled ? 'border-l-4 border-l-slate-300 opacity-80'
    : i.severity === 'error' ? 'border-l-4 border-l-red-400' : i.severity === 'warning' ? 'border-l-4 border-l-amber-300' : ''
  return (
    <div className={`panel p-3 ${edge}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            {handled ? (
              <span className="chip border-slate-300 bg-slate-100 text-slate-600">addressed · waiting for review</span>
            ) : (
              <SeverityChip severity={i.severity} />
            )}
            {i.area_label && <span className="chip border-slate-200 text-slate-500">{i.area_label}</span>}
            {i.count && <span className="chip border-slate-200 text-slate-500">{i.count} items</span>}
          </div>
          <div className="font-medium text-slate-900">{i.title}</div>
          {handled && <p className="mt-0.5 text-[12px] font-medium text-slate-500">{i.why}</p>}
          {i.what ? (
            <p className={`mt-1 text-slate-600 ${open ? '' : 'line-clamp-2'}`}>
              {i.what}
              {open && i.why && !handled && !simple && <span className="block pt-1 text-[12px] text-slate-400">{i.why}</span>}
            </p>
          ) : (
            i.why && <p className="mt-1 text-slate-600">{i.why}</p>
          )}
          {simple && i.what && i.why && !handled && (
            <p className="mt-1 text-[12px] text-slate-500"><span className="font-semibold">Why it matters: </span>{i.why}</p>
          )}
          {i.what && (
            <button onClick={() => setOpen(!open)} className="text-[12px] text-slate-500 hover:text-slate-800">
              {open ? 'Less' : 'More'}
            </button>
          )}
          <p className="mt-1 text-slate-800">
            <span className="font-semibold">What to do: </span>
            {i.todo}
          </p>
          {i.proposal && !handled && <p className="mt-1 font-mono text-[12px] text-indigo-800">{i.proposal}</p>}
          {i.kind === 'question' && i.event_id && <AnswerBox questionId={i.event_id} />}
          {i.kind === 'decision_batch' && i.targets && <SignAll targets={i.targets} />}
          {i.kind === 'reopened' && i.targets && <SignAll targets={i.targets} again />}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {hasEffect && (
            <div className="text-right text-[11px] leading-tight text-slate-500">
              <div>
                Federal <b className="num text-slate-800">{fmtEffect(i.effect.federal)}</b>
              </div>
              <div>
                California <b className="num text-slate-800">{fmtEffect(i.effect.california)}</b>
              </div>
              <div className="text-slate-400">estimated</div>
            </div>
          )}
          {href && (
            <Link to={href} className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700">
              Open →
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

// One review for decisions recorded together.
function SignAll({ targets, again = false }: { targets: string[]; again?: boolean }) {
  const { person } = useSession()
  const post = usePostBatch()
  const level = (['reviewer', 'partner'] as const).find((l) => l === person?.role)
  if (!level || !person?.can.includes('signoff')) return null
  return (
    <div className="mt-1.5">
      <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700" disabled={post.isPending}
        onClick={() => post.mutate(targets.map((t) => ({ type: 'signoff', target: t, payload: { level } })))}>
        {post.isPending ? 'Signing…' : `${again ? 'Sign again' : 'Sign off'} all ${targets.length} as ${level}`}
      </button>
      {post.error && <span className="ml-2 text-[12px] text-red-700">{(post.error as Error).message}</span>}
    </div>
  )
}

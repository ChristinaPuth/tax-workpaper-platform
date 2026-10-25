// Can this return be filed? The firm's twelve required steps, derived from the work, plus everything else
// that blocks filing - each with what is left and where to go. Nothing here is ticked by hand.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { GateStep } from '../api'
import { ActivityPanel } from '../components/ActivityPanel'
import { Ref } from '../components/Ref'
import { useGate, useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'
import { fmtTime } from '../format'
import { hrefFor } from '../refs'
import { Replay } from './Replay'
import { useMarkVisited } from '../queries'

const STATUS: Record<GateStep['status'], { icon: string; cls: string; label: string }> = {
  done: { icon: '✓', cls: 'border-emerald-200 bg-emerald-50 text-emerald-700', label: 'done' },
  open: { icon: '○', cls: 'border-amber-200 bg-amber-50 text-amber-800', label: 'to do' },
  later: { icon: '…', cls: 'border-slate-200 bg-slate-50 text-slate-500', label: 'comes later' },
}

export function FilingPage() {
  useMarkVisited('filing')
  const [params, setParams] = useSearchParams()
  const replay = params.get('tab') === 'replay'
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <div className="flex gap-1 border-b border-slate-200">
          {([['steps', 'Can we file?'], ['replay', 'Season replay']] as const).map(([k, label]) => (
            <button key={k} onClick={() => setParams(k === 'steps' ? {} : { tab: 'replay' })}
              className={`-mb-px border-b-2 px-3 py-1.5 text-[13px] font-medium ${(k === 'replay') === replay ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>
        {replay ? <Replay /> : <Steps />}
      </div>
    </div>
  )
}

function Steps() {
  const { data: gate } = useGate()
  const version = useLatestVersion()
  if (!gate) return <div className="p-6 text-slate-400">Checking whether the return can be filed…</div>

  return (
    <div className="space-y-5">
      <div className="contents">
        {gate.filed && (
          <div className="rounded-lg border border-indigo-300 bg-indigo-50 p-4">
            <h1 className="text-lg font-semibold text-slate-900">Filed on {fmtTime(gate.filed.at)} by {gate.filed.by_name}</h1>
            <p className="text-slate-700">
              The return as filed is frozen: what was filed is kept exactly. Any change from here goes on the amendment
              (Form 1040-X) and is listed against the filed return.
            </p>
            <Link to="/reports?tab=versions&a=working&b=amended" className="text-[13px] text-indigo-700 hover:underline">
              Compare as filed vs amended →
            </Link>
          </div>
        )}
        <header className={`rounded-lg border p-4 ${gate.ready ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}>
          <h1 className="text-lg font-semibold text-slate-900">
            {gate.ready ? 'Ready to file' : 'Not ready to file yet'}
          </h1>
          <p className="text-slate-700">
            {gate.summary.steps_done} of {gate.summary.steps_total} required steps done
            {gate.summary.blockers ? ` · ${gate.summary.blockers} blocker${gate.summary.blockers > 1 ? 's' : ''}` : ''}.
            {' '}Every step is worked out from the file and the work done on it.
          </p>
          {gate.ready && !gate.filed && <FileButton target={`ver:${version}`} />}
        </header>

        {gate.blockers.length > 0 && (
          <section>
            <h2 className="mb-2 font-semibold text-slate-800">Blocking filing</h2>
            <div className="divide-y divide-slate-100 rounded-md border border-red-200 bg-white">
              {gate.blockers.map((b, i) => {
                const href = b.kind === 'errors' ? '/findings' : b.target ? hrefFor(b.target) : b.kind === 'reopened' ? '/inbox' : null
                return (
                  <div key={i} className="flex items-center gap-2 px-3 py-2">
                    <span className="chip border-red-200 bg-red-50 text-red-700">{b.kind.replace('_', ' ')}</span>
                    <span className="min-w-0 flex-1">{b.title}</span>
                    {href && <Link to={href} className="text-[12px] text-indigo-700 hover:underline">Open →</Link>}
                  </div>
                )
              })}
            </div>
          </section>
        )}

        <section>
          <h2 className="mb-2 font-semibold text-slate-800">Required steps</h2>
          <ol className="space-y-2">
            {gate.steps.map((s) => (
              <li key={s.n} className="panel flex gap-3 p-3">
                <span className={`chip h-6 w-6 justify-center ${STATUS[s.status].cls}`}>{STATUS[s.status].icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="num text-slate-400">{s.n}.</span>
                    <span className="font-medium text-slate-900">{s.title}</span>
                    <span className={`chip ${STATUS[s.status].cls}`}>{STATUS[s.status].label}</span>
                  </div>
                  <p className="mt-0.5 text-slate-600">{s.detail}</p>
                  {s.progress && s.progress.total > 0 && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="h-1.5 w-48 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full bg-emerald-500" style={{ width: `${(100 * s.progress.done) / s.progress.total}%` }} />
                      </div>
                      <span className="num text-[11px] text-slate-500">{s.progress.done} / {s.progress.total}</span>
                    </div>
                  )}
                  {s.links.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {s.links.slice(0, 8).map((l) => <Ref key={l} id={l} />)}
                      {(s.progress ? s.progress.total - s.progress.done : s.links.length) > 8 && (
                        <span className="text-[11px] text-slate-400">
                          +{(s.progress ? s.progress.total - s.progress.done : s.links.length) - 8} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>

        {version && (
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <ActivityPanel target={`ver:${version}`} title="Sign-off on the whole return" />
          </section>
        )}
      </div>
    </div>
  )
}

// Filing is the partner's: once filed the return is frozen, so it asks before it does it.
function FileButton({ target }: { target: string }) {
  const { person } = useSession()
  const post = usePostEvent()
  const [sure, setSure] = useState(false)
  if (!person?.can.includes('file')) return <p className="mt-2 text-[13px] text-slate-600">The partner files the return.</p>
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      {!sure ? (
        <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700" onClick={() => setSure(true)}>File the return</button>
      ) : (
        <>
          <span className="text-[13px] text-slate-700">File now? The return will be frozen; later changes go on an amendment.</span>
          <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700" disabled={post.isPending}
            onClick={() => post.mutate({ type: 'file', target, payload: { jurisdictions: ['federal', 'california'] } })}>Yes, file</button>
          <button className="btn" onClick={() => setSure(false)}>Cancel</button>
        </>
      )}
      {post.error && <span className="text-[12px] text-red-700">{(post.error as Error).message}</span>}
    </div>
  )
}

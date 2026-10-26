// Form 8867 due diligence: the knowledge requirements for each dependent's credit, worked out from the file.
// The preparer confirms each item; the checklist is recorded as one due diligence decision, which completes
// step 8 of the filing gate. An item that is still a problem (an open SSN mismatch) cannot be confirmed.
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Ref } from '../components/Ref'
import { fmtTime } from '../format'
import { useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'

type Item = { id: string; person: string | null; credit: string | null; question: string; facts: string; status: 'ok' | 'check' | 'problem'; evidence: string[] }
type Checklist = { form: string; credits: string[]; items: Item[]; problems: string[]; recorded: { by: string; at: string; decision: string } | null }

const STATUS = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  check: 'border-amber-200 bg-amber-50 text-amber-800',
  problem: 'border-red-200 bg-red-50 text-red-700',
}

export function DueDiligencePage() {
  const { person, people } = useSession()
  const version = useLatestVersion()
  const { data } = useQuery({ queryKey: ['due-diligence', 'events'], queryFn: () => api<Checklist>('/due-diligence') })
  const post = usePostEvent()
  const [ticked, setTicked] = useState<Record<string, boolean>>({})
  const [decision, setDecision] = useState('Knowledge requirements met for each credit claimed; answers and documents kept in the file.')
  const [authority, setAuthority] = useState('IRC 6695(g); Treas. Reg. 1.6695-2')
  const groups = useMemo(() => {
    const m = new Map<string, Item[]>()
    data?.items.forEach((i) => m.set(i.person ?? 'General', [...(m.get(i.person ?? 'General') ?? []), i]))
    return [...m.entries()]
  }, [data])
  if (!data || !version) return <div className="p-6 text-slate-400">Working out the Form 8867 checklist…</div>

  const left = data.items.filter((i) => !ticked[i.id]).length
  const can = !!person?.can.includes('judgment')
  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const submit = () => post.mutate({
    type: 'judgment', target: `line:${version}:F8867.status`,
    payload: { kind: 'due_diligence', decision: decision.trim(), authority: authority.trim(), checklist: ticked },
  }, { onSuccess: () => setTicked({}) })

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <header className="space-y-1">
          <Link to="/filing" className="text-[12px] text-indigo-700 hover:underline">← Can we file?</Link>
          <h1 className="text-lg font-semibold text-slate-900">Form 8867 due diligence</h1>
          <p className="text-slate-600">
            For {data.credits.join(' and ')}. Each question is answered from the household record, the documents, the
            questionnaire and the issues. Confirm each one you have checked; the checklist is kept with the return.
          </p>
          {data.recorded && (
            <p className="rounded-md border border-emerald-300 bg-emerald-50 p-2 text-[13px] text-emerald-900">
              Recorded by {name(data.recorded.by)} on {fmtTime(data.recorded.at)}: {data.recorded.decision}
            </p>
          )}
          {data.problems.length > 0 && (
            <p className="rounded-md border border-red-300 bg-red-50 p-2 text-[13px] text-red-900">
              {data.problems.length} item{data.problems.length > 1 ? 's' : ''} cannot be confirmed yet - settle the issue behind {data.problems.length > 1 ? 'them' : 'it'} first.
            </p>
          )}
        </header>

        {groups.map(([who, items]) => (
          <section key={who} className="rounded-lg border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2 font-semibold text-slate-900">
              {who}{items[0].credit && <span className="ml-2 text-[12px] font-normal text-slate-500">{items[0].credit}</span>}
            </h2>
            <ul className="divide-y divide-slate-100">
              {items.map((i) => (
                <li key={i.id} className="flex gap-3 px-4 py-2.5">
                  <input type="checkbox" className="mt-1" aria-label={i.question} checked={!!ticked[i.id]}
                    disabled={!can || i.status === 'problem'} onChange={(e) => setTicked({ ...ticked, [i.id]: e.target.checked })} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className="font-medium text-slate-900">{i.question}</span>
                      <span className={`chip ${STATUS[i.status]}`}>{i.status === 'ok' ? 'supported' : i.status === 'check' ? 'check' : 'problem'}</span>
                    </div>
                    <p className="text-[13px] text-slate-600">{i.facts}</p>
                    {i.evidence.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">{i.evidence.map((r) => <Ref key={r} id={r} />)}</div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {can ? (
          <section className="space-y-2 rounded-lg border border-indigo-200 bg-white p-4">
            <h2 className="font-semibold text-slate-900">Record the checklist</h2>
            <textarea value={decision} onChange={(e) => setDecision(e.target.value)} rows={2} aria-label="Decision"
              className="w-full rounded-md border border-slate-300 px-2 py-1 text-[13px]" />
            <input value={authority} onChange={(e) => setAuthority(e.target.value)} aria-label="Authority"
              className="w-full rounded-md border border-slate-300 px-2 py-1 text-[13px]" />
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700"
                disabled={left > 0 || !decision.trim() || !authority.trim() || post.isPending} onClick={submit}>
                Record Form 8867 checklist
              </button>
              <span className="text-[12px] text-slate-500">{left ? `${left} of ${data.items.length} items left to confirm` : 'Every item confirmed'}</span>
            </div>
            {post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
          </section>
        ) : (
          <p className="text-[13px] text-slate-500">The preparer completes this checklist.</p>
        )}
      </div>
    </div>
  )
}

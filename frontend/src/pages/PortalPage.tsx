// The client's view of their return: where it stands, what we need from them, what it comes to, and - once
// the partner has signed it - their approval and e-signature (Form 8879 / FTB 8879). Plain language throughout.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type DocumentRow, type SummaryReport } from '../api'
import { AnswerBox } from '../components/ActivityPanel'
import { fmtTime, fmtValue } from '../format'
import { useGate, useInbox, useLatestVersion, usePostEvent, useReport, useSignoffs } from '../queries'
import { useSession } from '../session-context'

export function PortalPage() {
  const { person, people } = useSession()
  const { data: inbox } = useInbox()
  const { data: gate } = useGate()
  const { data: signoffs = [] } = useSignoffs()
  const version = useLatestVersion()
  const { data: docs = [] } = useQuery({ queryKey: ['documents'], queryFn: () => api<DocumentRow[]>('/documents') })
  const sent = docs.filter((d) => d.uploaded_by === 'client').length
  if (!person || !gate || !inbox) return <div className="p-6 text-slate-400">Loading your return…</div>

  const ret = `ver:${version}`
  const step = (n: number) => gate.steps.find((s) => s.n === n)!
  const partnerSigned = step(11).status === 'done'
  const questions = inbox.sections.find((s) => s.key === 'questions')?.items ?? []
  const clients = people.filter((p) => p.role === 'client')
  const approvals = signoffs.filter((s) => s.target === ret && s.level === 'client')
  const mine = approvals.filter((s) => s.actor === person.id).slice(-1)[0]
  // a reviewed return is past preparation as far as the client is concerned, whatever the firm still tracks
  const prepDone = step(10).status === 'done' || [2, 3, 4, 5, 6, 7, 8, 9].every((n) => step(n).status === 'done')

  const stages: [string, boolean, string][] = [
    ['Documents received', step(1).status === 'done', `${sent} from you, ${docs.length - sent} we obtained`],
    ['Being prepared', prepDone, prepDone ? 'Done' : 'Your preparer is checking every number against your documents'],
    ['Reviewed', step(10).status === 'done', step(10).status === 'done' ? 'A second accountant has reviewed it' : 'A second accountant reviews it'],
    ['Signed off by the partner', partnerSigned, partnerSigned ? 'Ready for you' : 'Comes after the review'],
    ['Your approval', step(12).status === 'done', step(12).status === 'done' ? 'Approved by both of you' : 'You and your spouse approve and sign'],
    ['Filed', false, 'We file with the IRS and California after you approve'],
  ]
  const current = stages.findIndex(([, done]) => !done)

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <header>
          <h1 className="text-lg font-semibold text-slate-900">Hello {person.name.split(' ')[0]} - your 2025 tax return</h1>
          <p className="text-slate-600">Married filing jointly with {clients.filter((c) => c.id !== person.id).map((c) => c.name).join(', ')}.</p>
        </header>

        <ol className="grid gap-2 sm:grid-cols-3">
          {stages.map(([label, done, note], i) => (
            <li key={label} className={`rounded-md border p-2 ${done ? 'border-emerald-200 bg-emerald-50' : i === current ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white'}`}>
              <div className="flex items-center gap-1.5 font-medium text-slate-900">
                <span className={`chip h-5 w-5 justify-center ${done ? 'border-emerald-300 bg-emerald-100 text-emerald-700' : 'border-slate-300 text-slate-500'}`}>{done ? '✓' : i + 1}</span>
                {label}
              </div>
              <p className="mt-0.5 text-[12px] text-slate-600">{note}</p>
            </li>
          ))}
        </ol>

        {questions.length > 0 && (
          <section>
            <h2 className="mb-2 font-semibold text-slate-800">We have {questions.length} question{questions.length > 1 ? 's' : ''} for you</h2>
            <div className="space-y-2">
              {questions.map((q) => (
                <div key={q.id} className="panel p-3">
                  <p className="font-medium text-slate-900">{q.title}</p>
                  <p className="text-[12px] text-slate-500">From {people.find((p) => p.id === q.actor)?.name ?? 'your preparer'}. Your answer is kept with your file.</p>
                  {q.event_id && <AnswerBox questionId={q.event_id} />}
                </div>
              ))}
            </div>
          </section>
        )}

        <AtAGlance final={partnerSigned} />

        <Approval partnerSigned={partnerSigned} mine={mine} approvals={approvals} clients={clients.map((c) => ({ id: c.id, name: c.name }))} ret={ret} />

        <section className="text-[13px] text-slate-600">
          You have sent us {sent} documents; we obtained {docs.length - sent} more (such as IRS records). <Link to="/documents" className="text-indigo-700 hover:underline">See your documents →</Link>
        </section>
      </div>
    </div>
  )
}

function AtAGlance({ final }: { final: boolean }) {
  const { data } = useReport<SummaryReport>('summary')
  if (!data) return null
  const row = (section: string, key: string) => data.sections.find((s) => s.key === section)?.rows.find((r) => r.key === key)
  const balance = (r: ReturnType<typeof row>, who: string) => {
    if (!r || r.working === null) return null
    const now = r.working, before = r.prior
    const say = (v: number | null) => v === null ? '—' : v > 0 ? `you owe ${fmtValue(v)}` : v < 0 ? `refund of ${fmtValue(-v)}` : 'nothing due'
    return (
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-400">{who}</div>
        <div className="text-lg font-semibold text-slate-900">{say(now)[0].toUpperCase() + say(now).slice(1)}</div>
        <div className="text-[12px] text-slate-500">Last year: {say(before)}</div>
      </div>
    )
  }
  const plain = [['F1040.9', 'Total income'], ['F1040.11', 'Adjusted gross income'], ['F1040.24', 'Total federal tax']] as const
  return (
    <section>
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="font-semibold text-slate-800">Your return at a glance</h2>
        {!final && <span className="chip border-amber-300 bg-amber-50 text-amber-800">draft - may still change</span>}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {balance(row('federal', 'F1040.37'), 'Federal (IRS)')}
        {balance(row('california', 'F540NR.97'), 'California (FTB)')}
      </div>
      <table className="mt-2 w-full text-[13px]">
        <tbody className="divide-y divide-slate-100">
          {plain.map(([key, label]) => {
            const r = row('federal', key)
            return r ? (
              <tr key={key}>
                <td className="py-1 text-slate-700">{label}</td>
                <td className="num py-1 text-right font-medium">{fmtValue(r.working)}</td>
                <td className="num py-1 pl-3 text-right text-[12px] text-slate-500">last year {fmtValue(r.prior)}</td>
              </tr>
            ) : null
          })}
        </tbody>
      </table>
    </section>
  )
}

type Approval = { event_id: number; actor: string; at: string; valid: boolean; changed: { node: string; what: string }[]; changed_count: number }

function Approval({ partnerSigned, mine, approvals, clients, ret }: {
  partnerSigned: boolean; mine: Approval | undefined; approvals: Approval[]; clients: { id: string; name: string }[]; ret: string
}) {
  const { person } = useSession()
  const post = usePostEvent()
  const { data: plain } = useQuery({ queryKey: ['labels'], queryFn: () => api<Record<string, string>>('/labels'), staleTime: Infinity })
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [consent, setConsent] = useState(false)
  const latest = (id: string) => approvals.filter((a) => a.actor === id).slice(-1)[0]

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold text-slate-900">Approve and sign</h2>
      {!partnerSigned && <p className="text-slate-600">Your return is not ready for approval yet. We will let you know when the partner has signed it off.</p>}
      <ul className="space-y-1 text-[13px]">
        {clients.map((c) => {
          const a = latest(c.id)
          return (
            <li key={c.id} className="flex items-center gap-2">
              <span className={`chip ${a?.valid ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : a ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 text-slate-500'}`}>
                {a?.valid ? '✓ approved' : a ? 'needs to approve again' : 'not yet'}
              </span>
              <span>{c.name}{a ? ` · signed ${fmtTime(a.at)}` : ''}</span>
            </li>
          )
        })}
      </ul>
      {mine?.valid && (
        <button className="text-[12px] text-slate-500 hover:text-slate-800 hover:underline" disabled={post.isPending}
          onClick={() => post.mutate({ type: 'undo', payload: { event_id: mine.event_id } })}>
          Withdraw my approval (before we file)
        </button>
      )}
      {mine && !mine.valid && (
        <div className="rounded-md border border-red-200 bg-red-50 p-2 text-[13px] text-red-900">
          Your return changed after you approved it ({mine.changed_count} item{mine.changed_count > 1 ? 's' : ''}), so your approval no longer holds:
          <ul className="ml-4 mt-1 list-disc">
            {mine.changed.slice(0, 5).map((c) => <li key={c.node}>{plain?.[c.node] ?? c.node}: {c.what}</li>)}
          </ul>
        </div>
      )}
      {partnerSigned && !mine?.valid && person?.role === 'client' && (
        <form className="space-y-2" onSubmit={(e) => {
          e.preventDefault()
          post.mutate({ type: 'signoff', target: ret, payload: { level: 'client', typed_name: name, pin, consent } },
            { onSuccess: () => { setPin(''); setConsent(false) } })
        }}>
          <label className="flex items-start gap-2 text-[13px] text-slate-700">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1"
              aria-label="I have reviewed this return and authorize e-filing" />
            I have reviewed this return and, to the best of my knowledge, it is true, correct and complete. I authorize the firm
            to file it electronically with the IRS (Form 8879) and California (FTB 8879).
          </label>
          <div className="flex flex-wrap gap-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={`Type your full name (${person.name})`} aria-label="Your full name"
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-[13px]" />
            <input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 5))} placeholder="5-digit PIN" aria-label="Your signature PIN"
              type="password" inputMode="numeric" autoComplete="off" className="w-32 rounded-md border border-slate-300 px-2 py-1 text-[13px]" />
            <button type="submit" disabled={!consent || !name.trim() || pin.length !== 5 || post.isPending}
              className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">Approve and sign</button>
          </div>
          <p className="text-[12px] text-slate-500">Your PIN is your electronic signature. Choose any five digits; we do not store it.</p>
          {post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
        </form>
      )}
    </section>
  )
}

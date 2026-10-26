// The engagement's plan on the Inbox: who is on it, the firm's deadlines (met, close, overdue), and work
// assigned to people that is not done yet.
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { fmtDate } from '../format'
import { useSession } from '../session-context'
import { Ref } from './Ref'

type Deadline = { what: string; date: string; kind: string; days_left: number; met: string | null; status: 'met' | 'extended' | 'outside' | 'overdue' | 'soon' | 'upcoming' }
type Assignment = { event_id: number; target: string; to: string; to_name: string; by_name: string; due: string | null; note: string | null; status: 'open' | 'done'; days_left: number | null }
type Plan = { as_of: string; team: { role: string; id: string; name: string }[]; assignments: Assignment[]; deadlines: Deadline[] }

const STATUS: Record<Deadline['status'], string> = {
  met: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  extended: 'border-sky-200 bg-sky-50 text-sky-700',
  overdue: 'border-red-200 bg-red-50 text-red-700',
  soon: 'border-amber-200 bg-amber-50 text-amber-800',
  upcoming: 'border-slate-200 bg-white text-slate-600',
  outside: 'border-slate-200 bg-slate-50 text-slate-500',
}

export function WorkPlan() {
  const { person } = useSession()
  const { data } = useQuery({ queryKey: ['assignments', 'events'], queryFn: () => api<Plan>('/assignments') })
  if (!data) return null
  const open = data.assignments.filter((a) => a.status === 'open')
  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-white p-3">
      <div className="mb-1.5 flex flex-wrap items-baseline gap-x-3 text-[12px] text-slate-500">
        <span className="section-title">Deadlines</span>
        <span>as of {fmtDate(data.as_of)}</span>
        <span>Team: {data.team.map((t) => `${t.name} (${t.role})`).join(' · ')}</span>
      </div>
      <ul className="grid gap-x-4 gap-y-0.5 text-[12px] sm:grid-cols-2">
        {data.deadlines.map((d) => (
          <li key={d.what} className="flex items-baseline gap-2">
            <span className="num w-20 shrink-0 text-slate-500">{fmtDate(d.date)}</span>
            <span className="min-w-0 flex-1 truncate" title={d.what}>{d.what}</span>
            <span className={`chip shrink-0 ${STATUS[d.status]}`}>
              {d.status === 'met' ? `met ${fmtDate(d.met!)}` : d.status === 'extended' ? `extended ${fmtDate(d.met!)}` : d.status === 'overdue' ? `${-d.days_left} d overdue`
                : d.status === 'outside' ? 'outside engagement' : `${d.days_left} d left`}
            </span>
          </li>
        ))}
      </ul>
      {open.length > 0 && (
        <div className="mt-2 border-t border-slate-100 pt-1.5">
          <div className="section-title mb-0.5">Assigned, not done yet</div>
          <ul className="space-y-0.5 text-[12px]">
            {open.map((a) => (
              <li key={a.event_id} className={`flex flex-wrap items-center gap-1.5 ${a.to === person?.id ? 'font-medium' : ''}`}>
                <Ref id={a.target} /> <span>→ {a.to === person?.id ? 'you' : a.to_name}</span>
                {a.note && <span className="text-slate-500">· {a.note}</span>}
                {a.due && <span className={a.days_left !== null && a.days_left < 0 ? 'text-red-700' : 'text-slate-400'}>· due {fmtDate(a.due)}</span>}
                <span className="text-slate-400">· by {a.by_name}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

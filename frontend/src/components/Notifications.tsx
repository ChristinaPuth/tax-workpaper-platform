// The bell: what is waiting for you - work assigned to you, questions addressed to you, deadlines close or past.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { fmtDate } from '../format'
import { hrefFor } from '../refs'
import { useSession } from '../session-context'

type Note = { kind: 'assignment' | 'question' | 'deadline'; target: string | null; at: string; due: string | null; title: string; urgent: boolean }

const ICON = { assignment: '→', question: '?', deadline: '⏱' }

export function NotificationsBell() {
  const { actor, person } = useSession()
  const [open, setOpen] = useState(false)
  const { data } = useQuery({ queryKey: ['notifications', actor], queryFn: () => api<{ count: number; urgent: number; items: Note[] }>('/me/notifications') })
  if (!data) return null
  const client = person?.role === 'client'
  return (
    <span className="relative">
      <button onClick={() => setOpen(!open)} aria-label={`${data.count} notifications`}
        className={`chip ${data.urgent ? 'border-red-300 bg-red-500/25 text-red-50' : 'border-slate-500 bg-white/10 text-slate-100'} hover:bg-white/20`}>
        🔔 {data.count}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 max-h-[70vh] w-[24rem] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-md border border-slate-200 bg-white text-slate-800 shadow-xl">
          <div className="border-b border-slate-100 px-3 py-2 text-[12px] font-medium">
            {data.count ? `${data.count} waiting for you` : 'Nothing waiting for you'}
          </div>
          <ul className="divide-y divide-slate-100 text-[12px]">
            {data.items.map((n, i) => {
              const href = client ? '/portal' : n.target ? hrefFor(n.target) : '/inbox'
              return (
                <li key={i} className="px-3 py-1.5">
                  <Link to={href ?? '/inbox'} onClick={() => setOpen(false)} className="flex gap-2 hover:text-indigo-700">
                    <span className={n.urgent ? 'text-red-600' : 'text-slate-400'}>{ICON[n.kind]}</span>
                    <span className="min-w-0 flex-1">{n.title}</span>
                    {n.due && n.kind === 'assignment' && <span className={`whitespace-nowrap ${n.urgent ? 'text-red-700' : 'text-slate-400'}`}>due {fmtDate(n.due)}</span>}
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </span>
  )
}

import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type WorkEvent } from '../api'
import { useSession } from '../session-context'
import { shortLabel } from '../refs'
import { useInbox } from '../queries'
import { SearchBar } from './SearchBar'
import { NavTrail } from './NavTrail'

const ROLE_LABEL: Record<string, string> = {
  preparer: 'Preparer',
  reviewer: 'Reviewer',
  partner: 'Partner',
  quality_reviewer: 'Quality reviewer',
  firm_administrator: 'Administrator',
  client: 'Client',
}

export function Layout() {
  const { actor, person, people, setActor, live, recent } = useSession()
  const { data: changes } = useQuery({
    queryKey: ['changes', actor],
    queryFn: () => api<{ count: number }>('/me/changes'),
  })
  const { data: inbox } = useInbox()
  const nav = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2.5 py-1 text-[13px] font-medium ${isActive ? 'bg-slate-700 text-white' : 'text-slate-300 hover:text-white'}`

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-11 shrink-0 items-center gap-4 bg-slate-900 px-4 text-white">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold">Workpaper</span>
          <span className="text-[12px] text-slate-400">Okafor-Lindqvist · 2025 · Married filing jointly</span>
        </div>
        <nav className="flex gap-1">
          <NavLink to="/inbox" className={nav}>
            Inbox
            {inbox && inbox.total > 0 && <span className="num ml-1.5 rounded-full bg-red-500 px-1.5 text-[10px] text-white">{inbox.total}</span>}
          </NavLink>
          <NavLink to="/return" className={nav}>
            Return
          </NavLink>
          <NavLink to="/documents" className={nav}>
            Documents
          </NavLink>
          <NavLink to="/findings" className={nav}>
            Findings
          </NavLink>
        </nav>
        <SearchBar />
        <div className="ml-auto flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[11px] text-slate-400" title={`Live updates: ${live}`}>
            <span className={`h-2 w-2 rounded-full ${live === 'open' ? 'bg-emerald-400' : live === 'connecting' ? 'bg-amber-400' : 'bg-red-400'}`} />
            live
          </span>
          {changes && changes.count > 0 && (
            <span className="chip border-indigo-400 bg-indigo-500/20 text-indigo-100" title="Changes by others since you last looked">
              {changes.count} new
            </span>
          )}
          <label className="flex items-center gap-2 text-[12px]">
            <span className="text-slate-400">Acting as</span>
            <select
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              className="rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-[12px] text-white"
            >
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {ROLE_LABEL[p.role] ?? p.role}
                  {p.credential ? `, ${p.credential}` : ''}
                </option>
              ))}
            </select>
          </label>
          {person && !person.sensitive_data_clearance && person.role !== 'client' && (
            <span className="chip border-amber-400 bg-amber-500/20 text-amber-100" title={person.note ?? ''}>
              no sensitive-data clearance
            </span>
          )}
        </div>
      </header>
      <NavTrail />
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
      <LiveToasts recent={recent} actor={actor} />
    </div>
  )
}

function LiveToasts({ recent, actor }: { recent: WorkEvent[]; actor: string }) {
  const { people } = useSession()
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const fresh = recent.filter((e) => e.actor !== actor && now - new Date(e.at).getTime() < 8000).slice(0, 3)
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 space-y-2">
      {fresh.map((e) => (
        <div key={e.id} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-[12px] shadow-lg">
          <b>{name(e.actor)}</b> {e.type.replace('_', ' ')}
          {e.target && <span className="font-mono text-slate-500"> {shortLabel(e.target)}</span>}
        </div>
      ))}
    </div>
  )
}

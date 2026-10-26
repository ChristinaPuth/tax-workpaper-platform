import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import type { WorkEvent } from '../api'
import { useSession } from '../session-context'
import { shortLabel } from '../refs'
import { useGate, useInbox } from '../queries'
import { SearchBar } from './SearchBar'
import { NavTrail } from './NavTrail'
import { HelpButton } from './Help'
import { ChangesChip } from './Changes'
import { BatchUndo } from './BatchUndo'
import { NotificationsBell } from './Notifications'

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
  const { data: inbox } = useInbox()
  const { data: gate } = useGate()
  const nav = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2 py-1 text-[13px] font-medium xl:px-2.5 ${isActive ? 'bg-slate-700 text-white' : 'text-slate-300 hover:text-white'}`

  return (
    <div className="flex h-full flex-col">
      <header className="flex min-h-11 shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 bg-slate-900 xl:gap-x-4 px-4 py-1.5 text-white">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold">Workpaper</span>
          <span className="hidden text-[12px] text-slate-400 2xl:inline">Okafor-Lindqvist · 2025 · Married filing jointly</span>
        </div>
        <nav className="flex flex-wrap gap-1">
          {person?.role === 'client' ? (
            // clients see their return, not the firm's workpaper
            <>
              <NavLink to="/portal" className={nav}>Your return</NavLink>
              <NavLink to="/documents" className={nav}>Documents</NavLink>
            </>
          ) : (
            <>
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
              <NavLink to="/reports" className={nav}>
                Reports
              </NavLink>
              <NavLink to="/filing" className={nav}>
                Filing
                {gate && (
                  <span className={`num ml-1.5 rounded-full px-1.5 text-[10px] ${gate.ready ? 'bg-emerald-500 text-white' : 'bg-slate-600 text-slate-200'}`}>
                    {gate.ready ? 'ready' : `${gate.summary.steps_done}/${gate.summary.steps_total}`}
                  </span>
                )}
              </NavLink>
            </>
          )}
        </nav>
        {person?.role !== 'client' && <SearchBar />}
        <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1">
          <HelpButton />
          {person?.role !== 'client' && <span className="flex items-center gap-1.5 text-[11px] text-slate-400" title={`Live updates: ${live}`}>
            <span className={`h-2 w-2 rounded-full ${live === 'open' ? 'bg-emerald-400' : live === 'connecting' ? 'bg-amber-400' : 'bg-red-400'}`} />
            <span className="hidden xl:inline">live</span>
          </span>}
          <NotificationsBell />
          <ChangesChip />
          <label className="flex items-center gap-2 text-[12px]">
            <span className="hidden text-slate-400 2xl:inline">Acting as</span>
            <select
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              className="max-w-[12rem] rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-[12px] text-white 2xl:max-w-none"
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
            <span className="chip border-amber-400 bg-amber-500/20 text-amber-100" title={`No sensitive-data clearance. ${person.note ?? ''}`}>
              no <span className="hidden xl:inline">sensitive-data&nbsp;</span>clearance
            </span>
          )}
        </div>
      </header>
      <NavTrail />
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
      <BatchUndo />
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

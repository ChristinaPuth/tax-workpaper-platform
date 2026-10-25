// Help for every level: the quick start (ticked from what you actually did), the glossary, and your settings.
// New staff get the simple view and the quick start opens on its own; experienced staff get the expert view.
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { GLOSSARY, GLOSSARY_TERMS } from '../glossary'
import { useMySettings, useUpdateSettings, useView } from '../queries'
import { useSession } from '../session-context'

// A term with a plain explanation: dotted underline when glossary hints are on, a tooltip always.
export function Term({ t, children }: { t: string; children?: ReactNode }) {
  const { glossary } = useView()
  const text = GLOSSARY[t]
  if (!text) return <>{children ?? t}</>
  return (
    <span title={text} className={glossary ? 'cursor-help underline decoration-slate-400 decoration-dotted underline-offset-2' : ''}>
      {children ?? t}
    </span>
  )
}

// Technical ids (line keys, rule and check ids): shown in the expert view only.
export function Tech({ children }: { children: ReactNode }) {
  const { simple } = useView()
  return simple ? null : <>{children}</>
}

type Tab = 'start' | 'glossary' | 'settings'

export function HelpButton() {
  const { actor, person } = useSession()
  const { data } = useMySettings()
  const [open, setOpen] = useState<Tab | null>(null)
  const steps = data?.quick_start ?? []
  const done = steps.filter((s) => s.done).length

  // the quick start opens on its own once per visit for people who have it on (new staff by default)
  useEffect(() => {
    if (!data?.settings.quick_start || !steps.length || done === steps.length) return
    const key = `workpaper.quickstart.shown.${actor}`
    try {
      if (sessionStorage.getItem(key)) return
      sessionStorage.setItem(key, '1')
    } catch {
      /* no storage: open it anyway */
    }
    setOpen('start')
  }, [data?.settings.quick_start, actor, steps.length, done])

  if (!person) return null
  return (
    <>
      <button onClick={() => setOpen(open ? null : steps.length ? 'start' : 'glossary')}
        className="flex items-center gap-1 rounded-md border border-slate-600 px-2 py-1 text-[12px] text-slate-200 hover:border-slate-400"
        title="Quick start, glossary and your settings" aria-label="Help">
        <span className="xl:hidden">?</span><span className="hidden xl:inline">Help</span>
        {data?.settings.quick_start && steps.length > 0 && done < steps.length && (
          <span className="num rounded-full bg-indigo-500 px-1.5 text-[10px] text-white">{done}/{steps.length}</span>
        )}
      </button>
      {open && <HelpPanel tab={open} setTab={setOpen} onClose={() => setOpen(null)} />}
    </>
  )
}

function HelpPanel({ tab, setTab, onClose }: { tab: Tab; setTab: (t: Tab) => void; onClose: () => void }) {
  const { person } = useSession()
  const { data } = useMySettings()
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const tabs: [Tab, string][] = [
    ...(data?.quick_start.length ? [['start', 'Quick start'] as [Tab, string]] : []),
    ['glossary', 'Glossary'],
    ['settings', 'Settings'],
  ]
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/20" onClick={onClose}>
      <aside role="dialog" aria-label="Help" onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-md flex-col bg-white text-slate-800 shadow-2xl">
        <div className="flex items-center gap-1 border-b border-slate-200 px-4 py-2">
          {tabs.map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`rounded-md px-2.5 py-1 text-[13px] font-medium ${tab === k ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-800'}`}>
              {label}
            </button>
          ))}
          <button onClick={onClose} className="ml-auto text-slate-400 hover:text-slate-700" aria-label="Close help">✕</button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {tab === 'start' && <QuickStart name={person?.name.split(' ')[0] ?? ''} onGo={onClose} />}
          {tab === 'glossary' && <Glossary />}
          {tab === 'settings' && <Settings />}
        </div>
      </aside>
    </div>
  )
}

function QuickStart({ name, onGo }: { name: string; onGo: () => void }) {
  const { data } = useMySettings()
  if (!data) return null
  const steps = data.quick_start
  const done = steps.filter((s) => s.done).length
  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Welcome, {name}</h2>
        <p className="text-slate-600">
          {steps.length} things to try on this return. Each one ticks itself when you have done it. {done} of {steps.length} done.
        </p>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full bg-indigo-500" style={{ width: `${(100 * done) / Math.max(1, steps.length)}%` }} />
        </div>
      </div>
      <ol className="space-y-2">
        {steps.map((s, i) => (
          <li key={s.id} className={`rounded-md border p-2.5 ${s.done ? 'border-emerald-200 bg-emerald-50/50' : 'border-slate-200'}`}>
            <div className="flex items-baseline gap-2">
              <span className={`chip h-5 w-5 justify-center ${s.done ? 'border-emerald-300 bg-emerald-100 text-emerald-700' : 'border-slate-300 text-slate-500'}`}>
                {s.done ? '✓' : i + 1}
              </span>
              <span className="font-medium text-slate-900">{s.title}</span>
            </div>
            <p className="ml-7 mt-0.5 text-[13px] text-slate-600">{s.body}</p>
            {s.href && !s.done && (
              <Link to={s.href} onClick={onGo} className="ml-7 mt-1 inline-block text-[12px] text-indigo-700 hover:underline">Show me →</Link>
            )}
          </li>
        ))}
      </ol>
      <p className="text-[12px] text-slate-500">Words with a dotted underline have a plain explanation - hover over them, or see the Glossary tab.</p>
    </div>
  )
}

function Glossary() {
  const [q, setQ] = useState('')
  const terms = GLOSSARY_TERMS.filter((t) => !q || `${t} ${GLOSSARY[t]}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="space-y-3">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a term"
        className="w-full rounded-md border border-slate-300 px-2 py-1 text-[13px]" aria-label="Find a term" />
      <dl className="space-y-2">
        {terms.map((t) => (
          <div key={t}>
            <dt className="font-medium text-slate-900">{t}</dt>
            <dd className="text-[13px] text-slate-600">{GLOSSARY[t]}</dd>
          </div>
        ))}
        {!terms.length && <p className="text-slate-400">No term matches.</p>}
      </dl>
    </div>
  )
}

function Settings() {
  const { data } = useMySettings()
  const update = useUpdateSettings()
  if (!data) return null
  const s = data.settings
  const resetWidths = () => {
    try {
      Object.keys(localStorage).filter((k) => k.startsWith('workpaper.width.')).forEach((k) => localStorage.removeItem(k))
    } catch {
      /* nothing stored */
    }
    window.location.reload()
  }
  return (
    <div className="space-y-4">
      <p className="text-[12px] text-slate-500">{data.reason} Your choices below are kept for you on any computer.</p>
      <fieldset>
        <legend className="mb-1 font-medium text-slate-900">View</legend>
        {(['simple', 'expert'] as const).map((m) => (
          <label key={m} className="flex items-start gap-2 py-1">
            <input type="radio" name="mode" checked={s.mode === m} onChange={() => update.mutate({ mode: m })} className="mt-1" />
            <span>
              <span className="font-medium capitalize">{m}</span>
              <span className="block text-[12px] text-slate-500">
                {m === 'simple'
                  ? 'Plain labels and explanations; technical ids (line keys, rule and check ids) hidden.'
                  : 'Everything, including line keys, rule ids and check ids - denser.'}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={s.glossary} onChange={(e) => update.mutate({ glossary: e.target.checked })} className="mt-1" />
        <span>
          <span className="font-medium">Underline terms that have an explanation</span>
          <span className="block text-[12px] text-slate-500">Hover still explains them when this is off.</span>
        </span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={s.quick_start} onChange={(e) => update.mutate({ quick_start: e.target.checked })} className="mt-1" />
        <span>
          <span className="font-medium">Open the quick start when I start</span>
          <span className="block text-[12px] text-slate-500">Until every step is done.</span>
        </span>
      </label>
      <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
        <button className="btn" onClick={() => update.mutate('reset')} disabled={!data.changed.length}>Back to my defaults</button>
        <button className="btn" onClick={resetWidths}>Reset column widths</button>
      </div>
    </div>
  )
}

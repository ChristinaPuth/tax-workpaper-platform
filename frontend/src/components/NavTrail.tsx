// Where am I, and how did I get here: the pages visited in this tab, each one a step back.
// Going back (browser back, the Back button or a crumb) trims the trail instead of growing it.
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useNavigationType } from 'react-router-dom'
import { FORM_NAME } from '../format'

interface Crumb {
  path: string
  label: string
}

const MAX = 6

function labelFor(pathname: string, search: string): string | null {
  const q = new URLSearchParams(search)
  if (pathname === '/inbox') return 'Inbox'
  if (pathname === '/return') {
    const line = q.get('line')
    const form = q.get('form')
    if (line) return line
    return form ? FORM_NAME[form] ?? form : 'Return'
  }
  if (pathname === '/documents') return 'Documents'
  if (pathname === '/filing') return 'Filing'
  const doc = pathname.match(/^\/documents\/([^/]+)$/)
  if (doc) return `${doc[1]}${q.get('page') ? ` p${q.get('page')}` : ''}`
  if (pathname === '/findings') {
    if (q.get('id')) return `Issue ${q.get('id')}`
    if (q.get('check')) return `Issues ${q.get('check')}`
    return 'Findings'
  }
  return null // e.g. /value/ev-..., which redirects straight to a document
}

export function NavTrail() {
  const location = useLocation()
  const type = useNavigationType()
  const navigate = useNavigate()
  const [trail, setTrail] = useState<Crumb[]>([])

  useEffect(() => {
    const label = labelFor(location.pathname, location.search)
    if (!label) return
    const path = location.pathname + location.search
    setTrail((t) => {
      const at = t.findIndex((c) => c.path === path)
      if (at >= 0) return t.slice(0, at + 1) // back to somewhere already on the trail
      if (type === 'REPLACE' && t.length) return [...t.slice(0, -1), { path, label }]
      return [...t, { path, label }].slice(-MAX)
    })
  }, [location.pathname, location.search, type])

  if (trail.length < 2) return null
  return (
    <div className="flex h-8 shrink-0 items-center gap-2 border-b border-slate-200 bg-white px-4 text-[12px]">
      <button onClick={() => navigate(-1)} className="rounded px-1.5 py-0.5 font-medium text-slate-600 hover:bg-slate-100">
        ← Back
      </button>
      <span className="text-slate-300">|</span>
      <nav aria-label="Trail" className="flex min-w-0 items-center gap-1 overflow-hidden">
        {trail.map((c, i) => {
          const last = i === trail.length - 1
          return (
            <span key={c.path} className="flex min-w-0 items-center gap-1">
              {i > 0 && <span className="text-slate-300">›</span>}
              {last ? (
                <span className="truncate font-medium text-slate-800">{c.label}</span>
              ) : (
                <Link to={c.path} className="truncate text-slate-500 hover:text-indigo-700">
                  {c.label}
                </Link>
              )}
            </span>
          )
        })}
      </nav>
    </div>
  )
}

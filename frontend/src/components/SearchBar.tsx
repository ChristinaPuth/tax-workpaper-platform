// One search box for everything, always in the top bar: amounts, lines, documents, people, values, findings.
// ⌘K / Ctrl+K focuses it; arrows move, Enter opens, Esc closes.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type SearchResult } from '../api'
import { fmtValue, formOf } from '../format'
import { hrefFor } from '../refs'

interface Hit {
  group: string
  key: string
  primary: string
  secondary?: string
  value?: string
  href: string | null
}

function flatten(r: SearchResult): Hit[] {
  const hits: Hit[] = []
  r.lines.forEach((l) =>
    hits.push({ group: 'Return lines', key: `l:${l.key}`, primary: l.label, secondary: l.key, value: fmtValue(l.value),
      href: `/return?v=${l.version}&form=${formOf(l.key)}&line=${l.key}` }))
  r.documents.forEach((d) =>
    hits.push({ group: 'Documents', key: `d:${d.id}`, primary: d.title, secondary: d.id, href: `/documents/${d.id}` }))
  r.findings.forEach((f) =>
    hits.push({ group: 'Issues', key: `f:${f.id}`, primary: f.title, secondary: f.id,
      // open what the issue is about (a line, else a value / page / document it cites), else the issue itself
      href: (() => {
        for (const prefix of ['line:', 'ev:', 'page:', 'doc:']) {
          const n = [...f.nodes, ...f.evidence].find((x) => x.startsWith(prefix))
          if (n) return hrefFor(n)
        }
        return `/findings?id=${f.id}`
      })() }))
  r.extracted_values.forEach((e) =>
    hits.push({ group: 'Values read from documents', key: `e:${e.id}`, primary: e.label, secondary: `${e.document_id} p${e.page}`,
      value: e.text_as_read, href: `/documents/${e.document_id}?page=${e.page}&ev=${e.id}` }))
  r.people.forEach((p) =>
    hits.push({ group: 'People', key: `p:${p.id}`, primary: p.name, secondary: p.role.replace('_', ' '), href: null }))
  return hits
}

export function SearchBar() {
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 150)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        input.current?.focus()
        input.current?.select()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const { data } = useQuery({
    queryKey: ['search', debounced],
    queryFn: () => api<SearchResult>(`/search?q=${encodeURIComponent(debounced)}&limit=8`),
    enabled: debounced.length > 0,
  })
  const hits = useMemo(() => (data && data.query.trim() === debounced ? flatten(data) : []), [data, debounced])
  useEffect(() => setActive(0), [debounced])

  const go = (h: Hit | undefined) => {
    if (!h?.href) return
    navigate(h.href)
    setOpen(false)
    input.current?.blur()
  }

  let lastGroup = ''
  return (
    <div className="relative w-80">
      <input
        ref={input}
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((a) => Math.min(a + 1, hits.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((a) => Math.max(a - 1, 0))
          } else if (e.key === 'Enter') {
            go(hits[active])
          } else if (e.key === 'Escape') {
            setOpen(false)
            input.current?.blur()
          }
        }}
        placeholder="Search the whole return: amounts, lines, documents, issues…"
        className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-1 text-[12px] text-white placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none"
        aria-label="Search"
      />
      <kbd className="pointer-events-none absolute right-2 top-1.5 text-[10px] text-slate-400">⌘K</kbd>
      {open && debounced && (
        <div className="absolute left-0 top-full z-50 mt-1 max-h-[70vh] w-[28rem] overflow-y-auto rounded-md border border-slate-200 bg-white text-slate-800 shadow-xl">
          {data?.amount !== null && data?.amount !== undefined && (
            <div className="border-b border-slate-100 px-3 py-1.5 text-[11px] text-slate-500">
              Amounts equal to <b className="num">{fmtValue(data.amount)}</b> first, then text matches
            </div>
          )}
          {hits.length === 0 && <div className="px-3 py-3 text-slate-400">{data ? 'No matches.' : 'Searching…'}</div>}
          {hits.map((h, idx) => {
            const header = h.group !== lastGroup ? h.group : null
            lastGroup = h.group
            return (
              <div key={h.key}>
                {header && <div className="section-title bg-slate-50 px-3 pb-0.5 pt-2">{header}</div>}
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(idx)}
                  onClick={() => go(h)}
                  disabled={!h.href}
                  className={`flex w-full items-center gap-2 px-3 py-1.5 text-left ${idx === active ? 'bg-indigo-50' : ''} disabled:cursor-default`}
                >
                  <span className="min-w-0 flex-1 truncate">{h.primary}</span>
                  {h.secondary && <span className="font-mono text-[11px] text-slate-400">{h.secondary}</span>}
                  {h.value && <span className="num w-24 truncate text-right text-slate-600">{h.value}</span>}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

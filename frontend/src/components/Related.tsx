// What an item is connected to beyond its computation: the same line last year, the related returns it
// depends on (who prepares them, whether they are in the file), and links people made - with a way to add one.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { fmtTime, fmtValue } from '../format'
import { useLatestVersion, usePostEvent } from '../queries'
import { useSession } from '../session-context'
import { Ref } from './Ref'

type Related = {
  prior_year: { year: number; value: number | string; label: string | null } | null
  related_returns: { who: string; return: string; prepared_by: string; in_this_packet: string | false; documents: string[]; why: string }[]
  links: { event_id: number; other: string; note: string | null; by_name: string; at: string }[]
}

// What a person types ("D31", "F-017", "SchA.8a", "doc:D31") as a node id.
export function toNode(text: string, version: string): string {
  const t = text.trim()
  if (/^(line|doc|page|ev|finding|qa|msg|person|ver):/.test(t)) return t
  if (/^D\d{2}$/i.test(t)) return `doc:${t.toUpperCase()}`
  if (/^F-\d{3}$/i.test(t)) return `finding:${t.toUpperCase()}`
  if (/^ev-\d+$/.test(t)) return `ev:${t}`
  return `line:${version}:${t}`
}

export function RelatedSection({ node }: { node: string }) {
  const { person } = useSession()
  const version = useLatestVersion() ?? ''
  const { data } = useQuery({ queryKey: ['links', node], queryFn: () => api<Related>(`/links/${encodeURIComponent(node)}`) })
  const post = usePostEvent()
  const [adding, setAdding] = useState(false)
  const [to, setTo] = useState('')
  const [note, setNote] = useState('')
  if (!data) return null
  const can = !!person?.can.includes('link')
  const empty = !data.prior_year && !data.related_returns.length && !data.links.length
  if (empty && !can) return null
  return (
    <section>
      <div className="section-title mb-1">Related</div>
      <div className="space-y-1.5 rounded-md border border-slate-200 bg-white p-2 text-[12px]">
        {data.prior_year && (
          <div>
            <span className="text-slate-500">{data.prior_year.year} return:</span>{' '}
            <b className="num">{fmtValue(data.prior_year.value)}</b>
            {data.prior_year.label && <span className="text-slate-500"> · {data.prior_year.label}</span>}
          </div>
        )}
        {data.related_returns.map((r) => (
          <div key={r.who} className="rounded bg-slate-50 px-2 py-1">
            <div><b>{r.who}</b>: {r.return}</div>
            <div className="text-slate-500">
              Prepared by {r.prepared_by}. {r.in_this_packet ? `In this file: ${r.in_this_packet}.` : 'Not in this file.'} Related because {r.why}.
            </div>
          </div>
        ))}
        {data.links.map((l) => (
          <div key={l.event_id} className="flex flex-wrap items-center gap-1.5">
            <span className="text-slate-500">Linked to</span> <Ref id={l.other} />
            {l.note && <span>— {l.note}</span>}
            <span className="ml-auto text-[11px] text-slate-400">{l.by_name} · {fmtTime(l.at)}</span>
          </div>
        ))}
        {empty && <div className="text-slate-400">Nothing linked yet.</div>}
        {can && !adding && <button className="text-indigo-700 hover:underline" onClick={() => setAdding(true)}>+ Link to another item</button>}
        {adding && (
          <form className="flex flex-wrap gap-1" onSubmit={(e) => {
            e.preventDefault()
            post.mutate({ type: 'link', target: node, payload: { to: toNode(to, version), ...(note.trim() ? { note: note.trim() } : {}) } },
              { onSuccess: () => { setAdding(false); setTo(''); setNote('') } })
          }}>
            <input value={to} onChange={(e) => setTo(e.target.value)} aria-label="Link to" placeholder="D31, F-017 or SchA.8a"
              className="w-36 rounded-md border border-slate-300 px-2 py-1" />
            <input value={note} onChange={(e) => setNote(e.target.value)} aria-label="Why" placeholder="Why these belong together"
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1" />
            <button type="submit" disabled={!to.trim() || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">Link</button>
            <button type="button" className="btn" onClick={() => setAdding(false)}>Cancel</button>
            {post.error && <p className="w-full text-red-700">{(post.error as Error).message}</p>}
          </form>
        )}
      </div>
    </section>
  )
}

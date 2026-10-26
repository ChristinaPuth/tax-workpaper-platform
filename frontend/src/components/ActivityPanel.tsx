// Everything people do on one node besides changing its number: sign-offs (and whether they still hold),
// verifications, notes, questions and review notes - one thread, with the actions this person may take.
import { useEffect, useMemo, useState } from 'react'
import { VERIFICATION_TYPES, type WorkEvent } from '../api'
import { fmtTime } from '../format'
import { openAttachment, usePostEvent, useSignoffs, useTargetEvents, useUpload } from '../queries'
import { useSession } from '../session-context'

const THREAD = 'note,question,answer,review_note,resolve_note,verify,signoff,judgment,attach,assign'
const LEVELS = ['preparer', 'reviewer', 'partner'] as const
const label = (s: string) => s.replace(/_/g, ' ')

export function ActivityPanel({ target, title = 'Review & notes' }: { target: string; title?: string }) {
  const { person, people } = useSession()
  const { data: events = [] } = useTargetEvents(target, THREAD)
  const { data: allSignoffs = [] } = useSignoffs()
  const post = usePostEvent()
  const sign = usePostEvent() // its own mutation, so a refused sign-off shows its reason next to the button
  const [mode, setMode] = useState<'note' | 'question' | 'review_note' | 'verify' | 'assign' | null>(null)
  const [due, setDue] = useState('')
  const [text, setText] = useState('')
  const [to, setTo] = useState('')
  const [blocking, setBlocking] = useState(true)
  const [method, setMethod] = useState<string>(VERIFICATION_TYPES[0])
  // an error belongs to whoever caused it, on this node: clear it when either changes
  const { reset: resetPost } = post
  const { reset: resetSign } = sign
  useEffect(() => { resetPost(); resetSign() }, [person?.id, target, resetPost, resetSign])

  const name = (id: string) => people.find((p) => p.id === id)?.name ?? id
  const can = (t: string) => !!person?.can.includes(t)
  const signoffs = allSignoffs.filter((s) => s.target === target)
  const resolved = useMemo(() => new Set(events.filter((e) => e.type === 'resolve_note' && !e.undone).map((e) => e.payload.event_id)), [events])
  const answers = useMemo(() => {
    const m = new Map<unknown, WorkEvent>()
    events.filter((e) => e.type === 'answer' && !e.undone).forEach((e) => m.set(e.payload.event_id, e))
    return m
  }, [events])
  // sign at your own level only; once your sign-off holds there is nothing to sign, if it reopened you sign again
  const myLevel = LEVELS.find((l) => l === person?.role)
  const mineAll = signoffs.filter((s) => s.actor === person?.id && s.level === myLevel)
  const mine = mineAll[mineAll.length - 1]

  const submit = () => {
    if (mode === 'verify') post.mutate({ type: 'verify', target, payload: { method, note: text.trim() || undefined } })
    else if (mode === 'question') post.mutate({ type: 'question', target, payload: { to, text } })
    else if (mode === 'assign') post.mutate({ type: 'assign', target, payload: { to, ...(due ? { due } : {}), ...(text.trim() ? { note: text.trim() } : {}) } })
    else if (mode === 'review_note') post.mutate({ type: 'review_note', target, payload: { text, blocking } })
    else if (mode) post.mutate({ type: 'note', target, payload: { text } })
    setText('')
    setDue('')
    setMode(null)
  }
  const valid = mode === 'verify' || (mode === 'assign' ? !!to : text.trim() && (mode !== 'question' || to))

  return (
    <section className="space-y-2">
      <div className="section-title">{title}</div>

      {/* sign-offs on this node, and whether they still hold */}
      <div className="rounded-md border border-slate-200 bg-white p-2">
        {signoffs.length === 0 && <div className="text-[12px] text-slate-400">Not signed off.</div>}
        {signoffs.map((s) => (
          <div key={s.event_id} className="py-0.5">
            <div className="flex items-center gap-2 text-[12px]">
              {s.valid ? (
                <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">✓ {s.level} sign-off</span>
              ) : (
                <span className="chip border-red-200 bg-red-50 text-red-700">reopened · {s.level}</span>
              )}
              <span className="text-slate-600">{name(s.actor)}</span>
              <span className="ml-auto text-[11px] text-slate-400">
                {fmtTime(s.at)} · covers {s.scope_size} item{s.scope_size > 1 ? 's' : ''}
              </span>
            </div>
            {!s.valid && (
              <ul className="ml-2 mt-1 list-disc pl-3 text-[12px] text-red-800">
                {s.changed.slice(0, 5).map((c) => (
                  <li key={c.node}>
                    <span className="font-mono">{c.node.split(':').slice(2).join(':') || c.node}</span>: {c.what}
                  </li>
                ))}
                {s.changed_count > 5 && <li>… and {s.changed_count - 5} more</li>}
              </ul>
            )}
            {s.valid && s.verified_since > 0 && (
              <div className="ml-2 text-[11px] text-slate-500">{s.verified_since} verification(s) added since — does not reopen.</div>
            )}
          </div>
        ))}
        {can('signoff') && myLevel && !mine?.valid && (
          <div className="mt-1.5 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-1.5">
            <button className="btn" disabled={sign.isPending}
              onClick={() => sign.mutate({ type: 'signoff', target, payload: { level: myLevel } })}>
              {mine ? `Sign again as ${myLevel}` : `Sign off as ${myLevel}`}
            </button>
            {sign.error && <span className="text-[12px] text-red-700">{(sign.error as Error).message}</span>}
          </div>
        )}
      </div>

      {/* the thread */}
      {events.filter((e) => e.type !== 'signoff' && e.type !== 'resolve_note' && e.type !== 'answer').length > 0 && (
        <div className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
          {events
            .filter((e) => !['signoff', 'resolve_note', 'answer'].includes(e.type))
            .map((e) => {
              const isResolved = resolved.has(e.id)
              const answer = answers.get(e.id)
              return (
                <div key={e.id} className={`p-2 text-[12px] ${e.undone ? 'opacity-50' : ''}`}>
                  <div className="flex items-center gap-2">
                    <span className={`chip ${KIND_STYLE[e.type] ?? 'border-slate-200 text-slate-600'}`}>
                      {e.type === 'review_note' && e.payload.blocking ? 'blocking review note' : label(e.type)}
                    </span>
                    {e.type === 'review_note' && isResolved && <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">resolved</span>}
                    <span className="text-slate-600">{name(e.actor)}</span>
                    {(e.type === 'question' || e.type === 'assign') && <span className="text-slate-400">→ {name(String(e.payload.to))}</span>}
                    {e.type === 'assign' && e.payload.due ? <span className="text-slate-400">· due {String(e.payload.due)}</span> : null}
                    <span className="ml-auto text-[11px] text-slate-400">{fmtTime(e.at)}</span>
                  </div>
                  {e.type === 'attach' ? <AttachedFile e={e} /> : <p className="mt-0.5 text-slate-800">
                    {e.type === 'verify' ? label(String(e.payload.method)) : e.type === 'judgment' ? String(e.payload.decision) : e.type === 'assign' ? String(e.payload.note ?? '') : String(e.payload.text ?? '')}
                    {e.type === 'verify' && e.payload.note ? ` — ${String(e.payload.note)}` : ''}
                  </p>}
                  {e.type === 'judgment' && <p className="text-[11px] text-slate-500">Authority: {String(e.payload.authority)}</p>}
                  {answer && (
                    <p className="mt-1 rounded bg-sky-50 px-2 py-1 text-sky-900">
                      <b>{name(answer.actor)}:</b> {String(answer.payload.text)}
                    </p>
                  )}
                  {e.type === 'question' && !answer && e.payload.to === person?.id && <AnswerBox questionId={e.id} />}
                  {e.type === 'review_note' && !isResolved && can('resolve_note') && (
                    <button className="mt-1 text-[12px] text-indigo-700 hover:underline"
                      onClick={() => post.mutate({ type: 'resolve_note', payload: { event_id: e.id, text: 'Resolved' } })}>
                      Resolve
                    </button>
                  )}
                </div>
              )
            })}
        </div>
      )}

      {/* actions */}
      <div className="flex flex-wrap gap-1">
        {can('verify') && <button className={tab(mode === 'verify')} onClick={() => setMode(mode === 'verify' ? null : 'verify')}>Mark verified</button>}
        {can('note') && <button className={tab(mode === 'note')} onClick={() => setMode(mode === 'note' ? null : 'note')}>Note</button>}
        {can('question') && <button className={tab(mode === 'question')} onClick={() => setMode(mode === 'question' ? null : 'question')}>Ask someone</button>}
        {can('review_note') && <button className={tab(mode === 'review_note')} onClick={() => setMode(mode === 'review_note' ? null : 'review_note')}>Review note</button>}
        {can('assign') && <button className={tab(mode === 'assign')} onClick={() => setMode(mode === 'assign' ? null : 'assign')}>Assign</button>}
        {can('attach') && <AttachButton target={target} />}
      </div>
      {mode && (
        <form className="space-y-1.5 rounded-md border border-indigo-200 bg-white p-2" onSubmit={(e) => { e.preventDefault(); if (valid) submit() }}>
          {mode === 'verify' && (
            <select value={method} onChange={(e) => setMethod(e.target.value)} className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]">
              {VERIFICATION_TYPES.map((m) => <option key={m} value={m}>{label(m)}</option>)}
            </select>
          )}
          {mode === 'assign' && (
            <div className="flex gap-1.5">
              <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Assign to" className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-[12px]">
                <option value="">Assign to whom?</option>
                {people.filter((p) => p.id.startsWith('st-')).map((p) => (
                  <option key={p.id} value={p.id}>{p.name} — {label(p.role)}</option>
                ))}
              </select>
              <input type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due date"
                className="rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
            </div>
          )}
          {mode === 'question' && (
            <select value={to} onChange={(e) => setTo(e.target.value)} className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]">
              <option value="">Ask whom?</option>
              {people.filter((p) => p.id !== person?.id).map((p) => (
                <option key={p.id} value={p.id}>{p.name} — {label(p.role)}</option>
              ))}
            </select>
          )}
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            placeholder={mode === 'verify' ? 'Optional: what you checked' : mode === 'question' ? 'Your question' : mode === 'assign' ? 'Optional: what to do' : 'Write a note'}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
          {mode === 'review_note' && (
            <label className="flex items-center gap-1.5 text-[12px] text-slate-600">
              <input type="checkbox" checked={blocking} onChange={(e) => setBlocking(e.target.checked)} /> Blocks filing until resolved
            </label>
          )}
          {post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
          <button type="submit" disabled={!valid || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">
            {mode === 'verify' ? 'Record verification' : mode === 'question' ? 'Send question' : mode === 'assign' ? 'Assign' : 'Add'}
          </button>
        </form>
      )}
      {!mode && post.error && <p className="text-[12px] text-red-700">{(post.error as Error).message}</p>}
    </section>
  )
}

// A stored file on the thread: name, size, the note given with it, and a button to open it.
function AttachedFile({ e }: { e: WorkEvent }) {
  const [err, setErr] = useState('')
  const id = e.payload.attachment_id as number | undefined
  const name = String(e.payload.filename ?? e.payload.ref ?? 'file')
  const size = Number(e.payload.size ?? 0)
  return (
    <div className="mt-0.5 text-slate-800">
      {id ? (
        <button className="text-indigo-700 hover:underline" disabled={e.undone}
          onClick={() => openAttachment(id, name).catch((x: Error) => setErr(x.message))}>📎 {name}</button>
      ) : <span>📎 {name}</span>}
      {size > 0 && <span className="ml-1 text-[11px] text-slate-400">{size < 1024 ? `${size} B` : `${Math.round(size / 1024)} KB`}</span>}
      {e.payload.note ? <span className="text-slate-600"> — {String(e.payload.note)}</span> : null}
      {err && <span className="ml-2 text-red-700">{err}</span>}
    </div>
  )
}

function AttachButton({ target }: { target: string }) {
  const upload = useUpload()
  const [file, setFile] = useState<File | null>(null)
  const [note, setNote] = useState('')
  const { reset } = upload
  useEffect(() => { setFile(null); reset() }, [target, reset])
  return (
    <>
      <label className="btn cursor-pointer">
        Attach file
        <input type="file" className="sr-only" aria-label="Attach file"
          onChange={(ev) => { setFile(ev.target.files?.[0] ?? null); upload.reset(); ev.target.value = '' }} />
      </label>
      {file && (
        <form className="flex w-full flex-wrap items-center gap-1.5 rounded-md border border-indigo-200 bg-white p-2 text-[12px]"
          onSubmit={(ev) => { ev.preventDefault(); upload.mutate({ target, file, note: note.trim() || undefined }, { onSuccess: () => { setFile(null); setNote('') } }) }}>
          <span className="font-medium">📎 {file.name}</span>
          <input value={note} onChange={(ev) => setNote(ev.target.value)} placeholder="Optional: what this file shows"
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1" />
          <button type="submit" disabled={upload.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">
            {upload.isPending ? 'Uploading…' : 'Upload'}
          </button>
          <button type="button" className="btn" onClick={() => setFile(null)}>Cancel</button>
        </form>
      )}
      {upload.error && <p className="w-full text-[12px] text-red-700">{(upload.error as Error).message}</p>}
    </>
  )
}

const KIND_STYLE: Record<string, string> = {
  attach: 'border-slate-300 bg-slate-50 text-slate-700',
  verify: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  question: 'border-sky-200 bg-sky-50 text-sky-700',
  assign: 'border-violet-200 bg-violet-50 text-violet-700',
  review_note: 'border-amber-200 bg-amber-50 text-amber-800',
  judgment: 'border-indigo-200 bg-indigo-50 text-indigo-700',
}

function tab(active: boolean) {
  return `btn ${active ? 'border-indigo-400 bg-indigo-50 text-indigo-800' : ''}`
}

export function AnswerBox({ questionId }: { questionId: number }) {
  const post = usePostEvent()
  const [text, setText] = useState('')
  return (
    <form className="mt-1 flex gap-1" onSubmit={(e) => { e.preventDefault(); if (text.trim()) post.mutate({ type: 'answer', payload: { event_id: questionId, text } }) }}>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Your answer"
        className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-[12px]" />
      <button type="submit" disabled={!text.trim() || post.isPending} className="btn border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700">Reply</button>
      {post.error && <span className="text-[12px] text-red-700">{(post.error as Error).message}</span>}
    </form>
  )
}

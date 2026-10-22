// Renders a simulated source page: the printed text, with every extracted value marked where it
// appears and the selected one highlighted. The renderer only needs character spans, so a real
// page image with layout boxes can replace it without touching the views that use it.
import type { PageField } from '../api'

interface Props {
  text: string
  fields: PageField[]
  activeEv?: string | null
  onSelect?: (evId: string) => void
}

export function PageText({ text, fields, activeEv, onSelect }: Props) {
  const spans = fields
    .filter((f) => f.span)
    .map((f) => ({ ...f.span!, f }))
    .sort((a, b) => a.start - b.start || b.end - a.end)

  const parts: React.ReactNode[] = []
  let at = 0
  for (const s of spans) {
    if (s.start < at) continue // overlapping reading of the same characters: keep the first
    if (s.start > at) parts.push(text.slice(at, s.start))
    const active = s.f.ev_id === activeEv
    const lowConf = s.f.confidence < 0.8
    parts.push(
      <mark
        key={s.f.ev_id}
        id={`ev-${s.f.ev_id}`}
        title={`${s.f.label} · read "${s.f.text_as_read}" · confidence ${s.f.confidence}`}
        onClick={() => onSelect?.(s.f.ev_id)}
        className={
          'cursor-pointer rounded-sm px-0.5 ' +
          (active
            ? 'bg-amber-300 text-slate-900 ring-2 ring-amber-400'
            : lowConf
              ? 'bg-red-100 text-red-900 underline decoration-red-400 decoration-dotted'
              : s.f.flows_to.length
                ? 'bg-indigo-50 text-slate-900 underline decoration-indigo-300 decoration-dotted underline-offset-2 hover:bg-indigo-100'
                : 'bg-transparent text-slate-900 underline decoration-slate-300 decoration-dotted underline-offset-2 hover:bg-slate-100')
        }
      >
        {text.slice(s.start, s.end)}
      </mark>,
    )
    at = s.end
  }
  if (at < text.length) parts.push(text.slice(at))

  return (
    <div className="whitespace-pre-wrap break-words font-mono text-[12.5px] leading-6 text-slate-700">{parts}</div>
  )
}

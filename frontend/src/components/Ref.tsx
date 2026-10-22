// One component for every reference in the packet's vocabulary (line:, ev:, doc:, page:, qa:, py:/ ...):
// it links where a view exists and always previews on hover.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type NodePreview } from '../api'
import { hrefFor, shortLabel } from '../refs'

export function Ref({ id, children, className = '' }: { id: string; children?: React.ReactNode; className?: string }) {
  const [hover, setHover] = useState(false)
  const { data } = useQuery({
    queryKey: ['node', id],
    queryFn: () => api<NodePreview>(`/nodes/${encodeURIComponent(id)}`),
    enabled: hover,
    staleTime: Infinity,
    retry: false,
  })
  const href = hrefFor(id)
  const body = children ?? <span className="font-mono">{shortLabel(id)}</span>
  const cls = `chip border-slate-200 bg-slate-50 text-slate-700 ${href ? 'hover:border-indigo-300 hover:text-indigo-700' : ''} ${className}`
  return (
    <span className="relative inline-block" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      {href ? (
        <Link to={href} className={cls}>
          {body}
        </Link>
      ) : (
        <span className={cls}>{body}</span>
      )}
      {hover && data && (
        <span className="pointer-events-none absolute left-0 top-full z-50 mt-1 w-72 rounded-md border border-slate-200 bg-white p-2 text-[11px] shadow-lg">
          <span className="block font-mono text-slate-400">{data.id}</span>
          <span className="block text-slate-700">{data.label}</span>
        </span>
      )}
    </span>
  )
}

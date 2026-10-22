import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type DocumentRow } from '../api'
import { fmtDate } from '../format'
import { StatusChip } from '../components/ui'

// Document index: every document, where it landed in the return, or why it did not.
export function DocumentsPage() {
  const { data: docs = [] } = useQuery({ queryKey: ['documents'], queryFn: () => api<DocumentRow[]>('/documents') })
  const [filter, setFilter] = useState<string>('all')
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    docs.forEach((d) => (c[d.landing_status] = (c[d.landing_status] ?? 0) + 1))
    return c
  }, [docs])
  const rows = filter === 'all' ? docs : docs.filter((d) => d.landing_status === filter)

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="mr-2 font-semibold text-slate-900">Documents</h1>
        {[['all', docs.length] as const, ...Object.entries(counts)].map(([k, n]) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`rounded-md px-2 py-0.5 text-xs ${filter === k ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            {k.replace(/_/g, ' ')} <span className="num opacity-70">{n}</span>
          </button>
        ))}
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-200 text-left text-[11px] uppercase tracking-wide text-slate-400">
            <th className="px-4 py-1.5 font-medium">Doc</th>
            <th className="py-1.5 font-medium">Title</th>
            <th className="py-1.5 font-medium">Received</th>
            <th className="py-1.5 font-medium">Pages</th>
            <th className="py-1.5 font-medium">Status</th>
            <th className="py-1.5 pr-4 text-right font-medium">Values landed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => {
            const unread = d.coverage?.not_located ?? 0
            return (
              <tr key={d.id} className="border-b border-slate-100 bg-white hover:bg-slate-50">
                <td className="px-4 py-1.5 font-mono text-[12px]">
                  <Link to={`/documents/${d.id}`} className="text-indigo-700 hover:underline">
                    {d.id}
                  </Link>
                </td>
                <td className="py-1.5 pr-2">
                  <Link to={`/documents/${d.id}`} className="hover:text-indigo-700">
                    {d.title}
                  </Link>
                  <span className="ml-1 text-[11px] text-slate-400">{d.document_type}</span>
                </td>
                <td className="num whitespace-nowrap py-1.5 pr-2 text-slate-500">{fmtDate(d.received_at)}</td>
                <td className="num py-1.5 text-slate-500">{d.page_count}</td>
                <td className="py-1.5">
                  <StatusChip status={d.landing_status} />
                  {d.extraction_status === 'partial' && (
                    <span className="chip ml-1 border-amber-200 bg-amber-50 text-amber-800">partially read</span>
                  )}
                </td>
                <td className="num py-1.5 pr-4 text-right text-slate-600">
                  {d.values_landed}/{d.values}
                  {unread > 0 && (
                    <span className="ml-1 text-[11px] text-amber-700" title="values whose reading is not found on the printed page">
                      · {unread} not on page
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

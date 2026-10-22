import { Navigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type ValueLayers } from '../api'

// ev:ev-0127 references don't carry their document; resolve it, then open the page at that value.
export function ValueRedirect() {
  const { id = '' } = useParams()
  const { data, error } = useQuery({ queryKey: ['value', id], queryFn: () => api<ValueLayers>(`/values/${id}`) })
  if (error) return <div className="p-6 text-red-700">{String(error)}</div>
  if (!data) return <div className="p-6 text-slate-400">Locating {id}…</div>
  return <Navigate replace to={`/documents/${data.document}?page=${data.page}&ev=${id}`} />
}

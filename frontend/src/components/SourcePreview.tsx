import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type PageView } from '../api'
import { PageText } from './PageText'
import { ValueLayers } from './ValueLayers'

// A source page shown inline, scrolled to and highlighting one extracted value.
export function SourcePreview({ doc, page, evId }: { doc: string; page: number; evId: string }) {
  const { data } = useQuery({
    queryKey: ['page', doc, page],
    queryFn: () => api<PageView>(`/documents/${doc}/pages/${page}`),
  })
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current?.querySelector(`#ev-${CSS.escape(evId)}`)
    el?.scrollIntoView({ block: 'center' })
  }, [data, evId])

  return (
    <div className="mt-2 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-2">
      <div className="flex items-center justify-between text-[11px] text-slate-500">
        <span>
          Source document <b className="font-mono text-slate-700">{doc}</b>, page {page}
        </span>
        <Link to={`/documents/${doc}?page=${page}&ev=${evId}`} className="text-indigo-700 hover:underline">
          Open document →
        </Link>
      </div>
      <div ref={box} className="max-h-56 overflow-auto rounded border border-slate-200 bg-white p-3 shadow-inner">
        {data ? <PageText text={data.printed_content} fields={data.fields} activeEv={evId} /> : '…'}
      </div>
      <ValueLayers evId={evId} />
    </div>
  )
}

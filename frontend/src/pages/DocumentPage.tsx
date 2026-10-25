import { useEffect, useMemo, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type DocumentDetail, type PageView } from '../api'
import { fmtDate, fmtValue, formOf } from '../format'
import { PageText } from '../components/PageText'
import { ValueLayers } from '../components/ValueLayers'
import { ActivityPanel } from '../components/ActivityPanel'
import { FindingCard, StatusChip } from '../components/ui'
import { Splitter } from '../components/Splitter'
import { useColumnWidth } from '../useColumnWidth'
import { useMarkVisited } from '../queries'

export function DocumentPage() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const { data: doc } = useQuery({ queryKey: ['document', id], queryFn: () => api<DocumentDetail>(`/documents/${id}`) })
  const page = Number(params.get('page') || doc?.pages[0] || 1)
  const activeEv = params.get('ev')
  useMarkVisited('trace', !!activeEv) // a value opened on its page: the end of following a number
  const { data: view } = useQuery({
    queryKey: ['page', id, page],
    queryFn: () => api<PageView>(`/documents/${id}/pages/${page}`),
    enabled: !!doc,
  })
  const textBox = useRef<HTMLDivElement>(null)
  const sideCol = useColumnWidth('document.side', 460, 320, 900)
  useEffect(() => {
    if (activeEv) textBox.current?.querySelector(`#ev-${CSS.escape(activeEv)}`)?.scrollIntoView({ block: 'center' })
  }, [view, activeEv])

  const select = (patch: Record<string, string>) => setParams({ page: String(page), ...(activeEv ? { ev: activeEv } : {}), ...patch })
  const landedFields = useMemo(() => (view?.fields ?? []).filter((f) => f.flows_to.length), [view])

  if (!doc) return <div className="p-6 text-slate-400">Loading {id}…</div>
  const landing = doc.landing

  return (
    <div className="flex h-full min-h-0">
      <section className="flex min-w-[320px] flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-4 py-2">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <Link to="/documents" className="hover:text-indigo-700">
              Documents
            </Link>
            <span>/</span>
            <span className="font-mono">{doc.id}</span>
          </div>
          <h1 className="font-semibold text-slate-900">{doc.title}</h1>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
            <span>{doc.issuer}</span>·<span>received {fmtDate(doc.received_at)}</span>·<span>uploaded by {doc.uploaded_by}</span>·
            <span className="font-mono">{doc.file_name}</span>
            {doc.marked_corrected && <span className="chip border-sky-200 bg-sky-50 text-sky-700">CORRECTED</span>}
          </div>
        </header>
        {doc.pages.length > 1 && (
          <div className="flex gap-1 border-b border-slate-200 bg-white px-4 py-1.5">
            {doc.pages.map((p) => (
              <button
                key={p}
                onClick={() => setParams({ page: String(p) })}
                className={`num rounded px-2 py-0.5 text-xs ${p === page ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                p{p}
              </button>
            ))}
          </div>
        )}
        <div ref={textBox} className="min-h-0 flex-1 overflow-y-auto bg-slate-100 p-6">
          <div className="mx-auto max-w-3xl rounded-sm bg-white px-10 py-8 shadow">
            <div className="mb-4 flex justify-between text-[10px] uppercase tracking-wide text-slate-400">
              <span>{doc.file_name}</span>
              <span>
                page {page} of {doc.page_count} · simulated from printed content
              </span>
            </div>
            {view ? (
              <PageText text={view.printed_content} fields={view.fields} activeEv={activeEv} onSelect={(ev) => select({ ev })} />
            ) : (
              '…'
            )}
          </div>
        </div>
      </section>

      <Splitter side="right" width={sideCol.width} onChange={sideCol.setWidth} onReset={sideCol.reset} />
      <aside style={{ width: sideCol.width }} className="min-w-[300px] shrink space-y-4 overflow-y-auto bg-slate-50 p-4">
        <section>
          <div className="section-title mb-1">Where this document went</div>
          <div className="rounded-md border border-slate-200 bg-white p-2.5">
            <div className="flex items-center gap-2">
              <StatusChip status={landing.status} />
              <span className="num text-slate-600">
                {landing.values_landed} of {landing.values} values used in the return
              </span>
            </div>
            {landing.reason && <p className="mt-1 text-slate-600">{landing.reason}</p>}
            {doc.extraction.reason && doc.extraction.status !== 'extracted' && (
              <p className="mt-1 text-amber-800">Extraction {doc.extraction.status}: {doc.extraction.reason}</p>
            )}
            {Object.keys(landing.landed).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {[...new Set(Object.values(landing.landed).flat())].map((k) => (
                  <Link
                    key={k}
                    to={`/return?form=${formOf(k)}&line=${k}`}
                    className="chip border-indigo-200 bg-white font-mono text-indigo-700 hover:bg-indigo-50"
                  >
                    {k}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>

        {activeEv && (
          <section className="space-y-3">
            <div>
              <div className="section-title mb-1">Selected value</div>
              <ValueLayers evId={activeEv} />
            </div>
            <ActivityPanel target={`ev:${activeEv}`} title="Review & notes on this value" />
          </section>
        )}

        <ActivityPanel target={`doc:${doc.id}`} title="Review & notes on this document" />

        {doc.findings.length > 0 && (
          <section className="space-y-1.5">
            <div className="section-title">Issues on this document</div>
            {doc.findings.map((f) => (
              <FindingCard key={f.id} f={f} compact={!!activeEv} />
            ))}
          </section>
        )}

        <section>
          <div className="section-title mb-1">Values on page {page}</div>
          <div className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
            {(view?.fields ?? []).length === 0 && <div className="p-2 text-slate-400">No values extracted on this page.</div>}
            {(view?.fields ?? []).map((f) => (
              <button
                key={f.ev_id}
                onClick={() => select({ ev: f.ev_id })}
                className={`flex w-full items-center gap-2 px-2 py-1 text-left ${f.ev_id === activeEv ? 'bg-amber-50' : 'hover:bg-slate-50'}`}
              >
                <span className="min-w-0 flex-1 truncate">{f.label}</span>
                {!f.span && <span className="chip border-red-200 bg-red-50 text-red-700">not on page</span>}
                {f.confidence < 0.8 && <span className="chip border-red-200 bg-red-50 text-red-700">conf {f.confidence}</span>}
                {f.flows_to.length > 0 && (
                  <span className="chip border-indigo-200 text-indigo-700" title={[...new Set(f.flows_to.map((t) => t.key))].join(', ')}>
                    → {new Set(f.flows_to.map((t) => t.key)).size}
                  </span>
                )}
                <span className="num w-24 text-right">{fmtValue(f.value)}</span>
              </button>
            ))}
          </div>
          <p className="mt-1 text-[11px] text-slate-400">{landedFields.length} on this page feed the return.</p>
        </section>
      </aside>
    </div>
  )
}

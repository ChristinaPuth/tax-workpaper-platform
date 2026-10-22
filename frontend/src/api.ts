// Thin client over the FastAPI backend. Every request carries the acting user (role switcher).

export const ACTOR_KEY = 'workpaper.actor'

export function currentActor(): string {
  try {
    return localStorage.getItem(ACTOR_KEY) || 'st-01'
  } catch {
    return 'st-01'
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-Actor': currentActor(), ...(init.headers || {}) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

// ------------------------------------------------------------------ types (mirror app/api.py)
export type Severity = 'error' | 'warning' | 'info'

export interface Person {
  id: string
  name: string
  role: string
  credential: string | null
  sensitive_data_clearance: boolean
  note: string | null
  can: string[]
}

export interface LineRow {
  key: string
  form: string
  line: string
  label: string
  value: number | string | null
  jurisdiction: string
  rule: string
  findings: Partial<Record<Severity, number>>
}

export interface Source {
  id: string
  kind: string
  document?: string
  page?: number
  field?: string
  value?: number | string | null
  text_as_read?: string
  confidence?: number
}

export interface TraceNode {
  id: string
  value: number | string | null
  rule: string | null
  inputs: TraceNode[]
  sources: Source[]
}

export interface Finding {
  id: string
  check: string
  title: string
  severity: Severity
  origin: string
  detail: string
  nodes: string[]
  evidence: string[]
  corrections: { line: string; current: unknown; proposed: unknown; category: string }[]
  federal_effect: number | null
  california_effect: number | null
  effect_note: string | null
  related: string[]
}

export interface LineDetail {
  key: string
  label: string
  form: string
  line: string
  latest_version: string
  by_version: Record<string, { value: number | string | null; rule: string; note: string | null }>
  rule: string
  rule_text: string | null
  note: string | null
  findings: Finding[]
}

export interface DocumentRow {
  id: string
  title: string
  document_type: string
  received_at: string
  page_count: number
  extraction_status: string
  landing_status: string
  values: number
  values_landed: number
  coverage: { located: number; not_located: number } | null
}

export interface Landing {
  status: string
  reason: string | null
  values: number
  values_landed: number
  landed: Record<string, string[]>
  values_not_landed: string[]
}

export interface DocumentDetail {
  id: string
  title: string
  document_type: string
  issuer: string
  belongs_to: string
  received_at: string
  uploaded_by: string
  file_name: string
  page_count: number
  marked_corrected?: boolean | null
  extraction: { status: string; values: number; reason: string | null }
  pages: number[]
  landing: Landing
  findings: Finding[]
}

export interface PageField {
  ev_id: string
  field: string
  label: string
  value: number | string | boolean | null
  value_type: string
  text_as_read: string
  confidence: number
  span: { start: number; end: number } | null
  flows_to: { version: string; key: string }[]
}

export interface PageView {
  document: string
  page: number
  printed_content: string
  fields: PageField[]
}

export interface ValueLayers {
  id: string
  document: string
  page: number
  field: string
  label: string
  printed: { found: boolean; text: string | null; context: string | null }
  extracted: { value: unknown; value_type: string; text_as_read: string; confidence: number }
  used: { key: string; label: string; value: number | string | null; rule: string; sources: number }[]
  version: string
  findings: Finding[]
}

export interface NodePreview {
  id: string
  kind: string
  label: string
  document: string | null
}

export interface WorkEvent {
  id: number
  at: string
  actor: string
  role: string
  type: string
  target: string | null
  payload: Record<string, unknown>
  batch_id: string | null
  undone?: boolean
}

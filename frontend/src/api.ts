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
  finding_refs: { id: string; severity: Severity }[]
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

// ------------------------------------------------------------------ working return (Plan C)
export type LineKind = 'engine' | 'adjusted' | 'propagated' | 'stale'

export interface WorkingLine {
  engine: number | string | null
  value: number | string | null
  kind: LineKind
  partial: boolean
}

export interface Adjustment {
  event_id: number
  key: string
  engine: number | string | null
  new: number | string
  actor: string
  reason: string
  at: string
  category: string | null
  effect: { category: string | null; federal: number | null; california: number | null; estimated: boolean }
}

export interface WorkingReturn {
  version: string
  lines: Record<string, WorkingLine>
  adjustments: Adjustment[]
  estimate: { federal: number; california: number; method: string }
  summary: Record<string, { engine: number | null; value: number | null; kind?: LineKind }>
  warnings: string[]
}

// ------------------------------------------------------------------ inbox
export interface InboxItem {
  id: string
  kind: 'finding' | 'group' | 'adjustment' | 'review_note' | 'question' | 'answer' | 'decision' | 'decision_batch' | 'reopened' | 'return'
  severity: Severity
  title: string
  what: string | null
  why: string
  todo: string
  proposal: string | null
  effect: { federal: number | null; california: number | null }
  area: string | null
  area_label: string | null
  target: string | null
  state: string
  check?: string
  count?: number
  event_id?: number
  actor?: string
  finding_id?: string
  handled_by?: string | null
  handled_at?: string | null
  targets?: string[] // decision_batch / reopened batch: the nodes one action signs off
  level?: 'preparer' | 'reviewer' | 'partner'
  finding_ids?: string[]
}

export interface InboxSection {
  key: string
  title: string
  hint: string | null
  items: InboxItem[]
  needs_you: boolean // false: shown for context (waiting on someone else), not counted
}

export interface Inbox {
  person: string
  role: string
  total: number
  sections: InboxSection[]
  empty_message: string | null
  areas: Record<string, string>
}

// ------------------------------------------------------------------ search
export interface SearchResult {
  query: string
  amount: number | null
  lines: { version: string; key: string; label: string; value: number | string | null; form: string }[]
  documents: { id: string; title: string; document_type: string }[]
  people: { id: string; name: string; role: string }[]
  extracted_values: { id: string; document_id: string; page: number; label: string; text_as_read: string }[]
  findings: Finding[]
}

export interface Overview {
  versions: { version: string; computed_at: string; trigger: string; summary: Record<string, Record<string, number>> }[]
  latest_version: string
}

// open | adjusted (changed, waiting for review) | reviewed - one rule shared with the Inbox
export interface FindingState {
  state: 'open' | 'adjusted' | 'decided' | 'reviewed'
  decision?: string
  authority?: string
  by?: string
  at?: string
  event_id?: number
  line?: string
}

// ------------------------------------------------------------------ sign-offs and the filing gate
export interface SignoffStatus {
  event_id: number
  target: string
  level: 'preparer' | 'reviewer' | 'partner'
  actor: string
  at: string
  valid: boolean
  scope_size: number
  changed: { node: string; what: string }[]
  changed_count: number
  verified_since: number
}

export interface GateStep {
  n: number
  title: string
  status: 'done' | 'open' | 'later'
  detail: string
  links: string[]
  progress: { done: number; total: number } | null
}

export interface Gate {
  ready: boolean
  steps: GateStep[]
  blockers: { kind: string; title: string; target: string | null; count?: number }[]
  summary: { steps_done: number; steps_total: number; blockers: number }
}

export const VERIFICATION_TYPES = [
  'agreed_to_source_document',
  'recalculated',
  'confirmed_with_client',
  'agreed_to_prior_year',
  'agreed_to_third_party_record',
] as const

export const JUDGMENT_KINDS = ['explanation', 'judgment', 'election', 'due_diligence', 'penalty'] as const

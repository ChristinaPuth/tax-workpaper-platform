import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type FindingState, type Gate, type Inbox, type LineRow, type Overview, type Severity, type SignoffStatus, type WorkEvent, type WorkingReturn } from './api'
import { useSession } from './session-context'

export function useOverview() {
  return useQuery({ queryKey: ['overview'], queryFn: () => api<Overview>('/overview'), staleTime: Infinity })
}

export function useLatestVersion(): string | undefined {
  return useOverview().data?.latest_version
}

export function useLines(version: string) {
  return useQuery({ queryKey: ['lines', version], queryFn: () => api<LineRow[]>(`/versions/${version}/lines`) })
}

// People's adjustments only apply to the current version; older engine versions are read-only history.
export function useWorking(version: string | undefined) {
  const latest = useLatestVersion()
  return useQuery({
    queryKey: ['working', version],
    queryFn: () => api<WorkingReturn>(`/working?version=${version}`),
    enabled: !!version && version === latest,
  })
}

export function useInbox() {
  const { actor } = useSession()
  return useQuery({ queryKey: ['inbox', actor], queryFn: () => api<Inbox>('/inbox') })
}

export function useFindingStates() {
  return useQuery({ queryKey: ['finding-states'], queryFn: () => api<Record<string, FindingState>>('/finding-states') })
}

// A line's issues split into still open (by severity) and already addressed by a change.
export function openFindings(row: LineRow, states: Record<string, FindingState> | undefined) {
  const open: Partial<Record<Severity, number>> = {}
  let addressed = 0
  for (const r of row.finding_refs) {
    if (states?.[r.id] && states[r.id].state !== 'open') addressed += 1
    else open[r.severity] = (open[r.severity] ?? 0) + 1
  }
  return { open, addressed }
}

export function useSignoffs() {
  return useQuery({ queryKey: ['signoffs'], queryFn: () => api<SignoffStatus[]>('/signoffs') })
}

export function useGate() {
  return useQuery({ queryKey: ['gate'], queryFn: () => api<Gate>('/gate') })
}

// Everything derived from the event log; refreshed after any write (here or, via SSE, by someone else).
export const LOG_DERIVED = ['events', 'changes', 'working', 'inbox', 'finding-states', 'signoffs', 'gate']

export function useRefreshLog() {
  const qc = useQueryClient()
  return () => LOG_DERIVED.forEach((key) => qc.invalidateQueries({ queryKey: [key] }))
}

export interface NewEvent {
  type: string
  target?: string | null
  payload: Record<string, unknown>
}

export function usePostEvent() {
  const refresh = useRefreshLog()
  return useMutation({
    mutationFn: (e: NewEvent) => api<WorkEvent>('/events', { method: 'POST', body: JSON.stringify(e) }),
    onSuccess: refresh,
  })
}

export function usePostBatch() {
  const refresh = useRefreshLog()
  return useMutation({
    mutationFn: (events: NewEvent[]) =>
      api<{ batch_id: string; events: WorkEvent[] }>('/events/batch', { method: 'POST', body: JSON.stringify({ events }) }),
    onSuccess: refresh,
  })
}

export function useTargetEvents(target: string, types?: string) {
  return useQuery({
    queryKey: ['events', target, types ?? 'all'],
    queryFn: () => api<WorkEvent[]>(`/events?target=${encodeURIComponent(target)}${types ? `&type=${types}` : ''}`),
  })
}

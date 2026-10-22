import { useQuery } from '@tanstack/react-query'
import { api, type LineRow } from './api'

export function useLines(version: string) {
  return useQuery({ queryKey: ['lines', version], queryFn: () => api<LineRow[]>(`/versions/${version}/lines`) })
}

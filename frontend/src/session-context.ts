import { createContext, useContext } from 'react'
import type { Person, WorkEvent } from './api'

export interface Session {
  actor: string
  person: Person | undefined
  people: Person[]
  setActor: (id: string) => void
  live: 'connecting' | 'open' | 'closed'
  recent: WorkEvent[]
}

export const Ctx = createContext<Session | null>(null)

export function useSession(): Session {
  const s = useContext(Ctx)
  if (!s) throw new Error('useSession outside SessionProvider')
  return s
}

// Who is acting (role switcher) and the live event stream, shared by every view.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ACTOR_KEY, api, currentActor, sandboxId, type Person, type WorkEvent } from './api'
import { Ctx, type Session } from './session-context'
import { LOG_DERIVED } from './queries'

export function SessionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [actor, setActorState] = useState(currentActor)
  const [live, setLive] = useState<Session['live']>('connecting')
  const [recent, setRecent] = useState<WorkEvent[]>([])
  const lastId = useRef(0)
  const { data: people = [] } = useQuery({ queryKey: ['people'], queryFn: () => api<Person[]>('/people') })

  const setActor = useCallback(
    (id: string) => {
      try {
        localStorage.setItem(ACTOR_KEY, id)
      } catch {
        /* private mode: the header still follows state */
      }
      setActorState(id)
      qc.invalidateQueries() // permissions and "what changed since I last looked" depend on who you are
    },
    [qc],
  )

  const isClient = actor.startsWith('cu-')
  useEffect(() => {
    if (isClient) { // the live stream carries the firm's internal work; clients refresh on their own actions
      setLive('closed')
      return
    }
    const es = new EventSource(`/api/stream?after=${lastId.current}&sandbox=${sandboxId()}`)
    es.onopen = () => setLive('open')
    es.onerror = () => setLive(es.readyState === EventSource.CLOSED ? 'closed' : 'connecting')
    const onEvent = (e: MessageEvent) => {
      const ev: WorkEvent = JSON.parse(e.data)
      lastId.current = Math.max(lastId.current, ev.id)
      setRecent((r) => [ev, ...r].slice(0, 20))
      LOG_DERIVED.forEach((key) => qc.invalidateQueries({ queryKey: [key] }))
    }
    // the server names each SSE message after the event type
    const types = ['note', 'review_note', 'resolve_note', 'question', 'answer', 'verify', 'adjust', 'judgment',
      'signoff', 'attach', 'assign', 'undo', 'view_sensitive']
    types.forEach((t) => es.addEventListener(t, onEvent))
    return () => es.close()
  }, [qc, isClient])

  const value = useMemo(
    () => ({ actor, person: people.find((p) => p.id === actor), people, setActor, live, recent }),
    [actor, people, setActor, live, recent],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

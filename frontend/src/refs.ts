// Where a reference in the packet's vocabulary (line:, ev:, doc:, page: ...) opens in the app.
import { formOf } from './format'

export function hrefFor(id: string): string | null {
  const [kind, ...rest] = id.split(':')
  const tail = rest.join(':')
  switch (kind) {
    case 'line': {
      const [version, key] = [tail.split(':')[0], tail.split(':').slice(1).join(':')]
      return `/return?v=${version}&form=${encodeURIComponent(formOf(key))}&line=${encodeURIComponent(key)}`
    }
    case 'ev':
      return `/value/${tail}`
    case 'doc':
      return `/documents/${tail}`
    case 'page': {
      const [doc, page] = tail.split('#')
      return `/documents/${doc}?page=${page}`
    }
    default:
      return null
  }
}

export function shortLabel(id: string): string {
  if (id.startsWith('line:')) return id.split(':').slice(2).join(':')
  if (id.startsWith('ev:') || id.startsWith('doc:')) return id.split(':')[1]
  if (id.startsWith('page:')) return id.slice(5).replace('#', ' p')
  return id
}

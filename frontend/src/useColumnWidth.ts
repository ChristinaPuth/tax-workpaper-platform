// Column widths remembered per browser - a convenience, not data, so localStorage is fine.
import { useCallback, useState } from 'react'

function load(key: string, fallback: number): number {
  try {
    const v = Number(localStorage.getItem(`workpaper.width.${key}`))
    return Number.isFinite(v) && v > 0 ? v : fallback
  } catch {
    return fallback
  }
}

export function useColumnWidth(key: string, initial: number, min: number, max: number) {
  const [width, setWidth] = useState(() => Math.min(max, Math.max(min, load(key, initial))))
  const set = useCallback(
    (w: number) => {
      const v = Math.round(Math.min(max, Math.max(min, w)))
      setWidth(v)
      try {
        localStorage.setItem(`workpaper.width.${key}`, String(v))
      } catch {
        /* private mode: the width still applies for this visit */
      }
    },
    [key, min, max],
  )
  return { width, setWidth: set, reset: () => set(initial) }
}

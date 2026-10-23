// A draggable divider between columns (widths live in useColumnWidth); double-click restores the default.
import { useEffect, useRef, useState } from 'react'

// side: which column the splitter resizes - the one to its 'left' (grows as you drag right)
// or to its 'right' (grows as you drag left).
export function Splitter({ side, width, onChange, onReset }: {
  side: 'left' | 'right'
  width: number
  onChange: (w: number) => void
  onReset: () => void
}) {
  const start = useRef<{ x: number; w: number } | null>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    if (!dragging) return
    const move = (e: MouseEvent) => {
      if (!start.current) return
      const dx = e.clientX - start.current.x
      onChange(start.current.w + (side === 'left' ? dx : -dx))
    }
    const up = () => {
      setDragging(false)
      start.current = null
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
  }, [dragging, onChange, side])

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      title="Drag to resize · double-click to reset"
      onMouseDown={(e) => {
        e.preventDefault()
        start.current = { x: e.clientX, w: width }
        setDragging(true)
      }}
      onDoubleClick={onReset}
      className={`group relative w-1 shrink-0 cursor-col-resize ${dragging ? 'bg-indigo-400' : 'bg-slate-200 hover:bg-indigo-300'}`}
    >
      <span className="absolute inset-y-0 -left-1 -right-1" />
    </div>
  )
}

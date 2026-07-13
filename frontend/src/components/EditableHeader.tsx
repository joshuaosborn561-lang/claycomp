import { useEffect, useRef, useState } from 'react'
import { Pencil, X } from 'lucide-react'

type Props = {
  label: string
  onRename: (label: string) => void
  onDelete?: () => void
  className?: string
}

export default function EditableHeader({ label, onRename, onDelete, className = '' }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(label)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(label)
  }, [label])

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const commit = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== label) onRename(trimmed)
    else setDraft(label)
    setEditing(false)
  }

  return (
    <div className={`group flex items-center gap-1 min-w-0 ${className}`}>
      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            if (e.key === 'Escape') {
              setDraft(label)
              setEditing(false)
            }
          }}
          className="w-full min-w-0 px-1 py-0.5 rounded border border-clay-300 bg-white text-[11px] font-semibold uppercase focus:outline-none focus:ring-1 focus:ring-clay-400"
        />
      ) : (
        <>
          <span className="truncate">{label}</span>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-200/60 shrink-0"
            title="Rename column"
          >
            <Pencil className="w-3 h-3 text-slate-400" />
          </button>
        </>
      )}
      {onDelete && !editing && (
        <button
          type="button"
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 shrink-0"
          title="Delete column"
        >
          <X className="w-3 h-3 text-red-500" />
        </button>
      )}
    </div>
  )
}

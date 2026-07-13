import { useEffect, useRef, useState } from 'react'

type Props = {
  value: string
  placeholder?: string
  onSave: (value: string) => void
  className?: string
}

export default function EditableCell({ value, placeholder = '—', onSave, className = '' }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(value)
  }, [value])

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const commit = () => {
    onSave(draft)
    setEditing(false)
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`w-full min-h-[28px] text-left px-1 -mx-1 rounded hover:bg-white/80 hover:ring-1 hover:ring-slate-200 truncate ${className}`}
        title="Click to edit"
      >
        {value || <span className="text-slate-300">{placeholder}</span>}
      </button>
    )
  }

  return (
    <input
      ref={inputRef}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') commit()
        if (e.key === 'Escape') {
          setDraft(value)
          setEditing(false)
        }
      }}
      className={`w-full min-h-[28px] px-1.5 -mx-1 rounded border border-clay-300 bg-white text-slate-800 focus:outline-none focus:ring-1 focus:ring-clay-400 ${className}`}
    />
  )
}

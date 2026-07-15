import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Paperclip, Sparkles, Upload } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { loadSample, streamChat, tableUploadAccept, uploadCsv } from '../api'
import { isAbortError, useJobs } from '../context/JobsContext'
import { useSettings } from '../context/SettingsContext'
import { useTable } from '../context/TableContext'
import type { ChatMessage } from '../types'

const STARTERS = [
  'Enrich all leads with nearest baseball team',
  'Normalize everyone\'s first name',
  'What\'s a good email opener for Joshua?',
  'Find the area nickname for each person',
]

type Props = Record<string, never>

export default function ChatMode(_props: Props) {
  const { settings } = useSettings()
  const { track } = useJobs()
  const { records, setRecords } = useTable()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Hey! I'm your enrichment assistant. Upload a CSV or Excel file (or use the sample data), then ask me to enrich leads, write openers, or answer questions about your list.\n\nTry: *\"Enrich all leads with nearest baseball team\"*",
    },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamBuffer, setStreamBuffer] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer])

  const send = async (text: string) => {
    if (!text.trim() || streaming) return

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text.trim() }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setStreaming(true)
    setStreamBuffer('')

    const assistantId = `a-${Date.now()}`
    let content = ''

    try {
      const updated = await track((signal) =>
        streamChat(nextMessages, records, (event) => {
          if (event.type === 'token') {
            content += event.content as string
            setStreamBuffer(content)
          }
          if (event.type === 'enrichment') {
            const line = `\n✓ **${event.name}**: ${event.preview}\n`
            content += line
            setStreamBuffer(content)
          }
        }, settings, signal),
      )

      if (updated) setRecords(updated)

      setMessages((m) => [
        ...m,
        { id: assistantId, role: 'assistant', content: content || 'Done.' },
      ])
    } catch (error) {
      if (isAbortError(error)) {
        setMessages((m) => [
          ...m,
          { id: assistantId, role: 'assistant', content: 'Stopped.' },
        ])
      } else {
        setMessages((m) => [
          ...m,
          { id: assistantId, role: 'assistant', content: 'Something went wrong. Check that the server is running.' },
        ])
      }
    } finally {
      setStreamBuffer('')
      setStreaming(false)
    }
  }

  const handleUpload = async (file: File) => {
    try {
      const { records: next, count } = await uploadCsv(file)
      setRecords(next)
      setMessages((m) => [
        ...m,
        {
          id: `sys-${Date.now()}`,
          role: 'assistant',
          content: `Loaded **${count} leads** from \`${file.name}\`. What would you like to enrich?`,
        },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          id: `sys-${Date.now()}`,
          role: 'assistant',
          content: `Could not import \`${file.name}\`: ${err instanceof Error ? err.message : 'Upload failed'}`,
        },
      ])
    }
  }

  return (
    <div className="h-full flex flex-col max-w-3xl mx-auto w-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.map((msg) => (
          <Message key={msg.id} message={msg} />
        ))}

        {streamBuffer && (
          <Message
            message={{ id: 'streaming', role: 'assistant', content: streamBuffer }}
            streaming
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Starters */}
      {messages.length <= 1 && (
        <div className="px-4 pb-3 flex flex-wrap gap-2 justify-center">
          {STARTERS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs px-3 py-1.5 rounded-full border border-slate-200 bg-white text-slate-600 hover:border-clay-300 hover:text-clay-700 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="shrink-0 p-4 border-t border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center gap-1 mb-2 px-1">
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <Paperclip className="w-3 h-3" />
            Upload CSV / Excel
          </button>
          <button
            onClick={async () => {
              const { records: next, count } = await loadSample()
              setRecords(next)
              setMessages((m) => [
                ...m,
                {
                  id: `sys-${Date.now()}`,
                  role: 'assistant',
                  content: `Loaded **${count} sample leads**. Try asking me to enrich them!`,
                },
              ])
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <Upload className="w-3 h-3" />
            Sample data
          </button>
          <span className="text-[11px] text-slate-300 ml-auto">{records.length} leads</span>
        </div>

        <div className="flex items-end gap-2 bg-white rounded-2xl border border-slate-200 shadow-soft px-4 py-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Ask anything about your leads…"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none max-h-32"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || streaming}
            className="shrink-0 w-8 h-8 rounded-xl bg-clay-600 hover:bg-clay-700 disabled:opacity-30 disabled:hover:bg-clay-600 text-white flex items-center justify-center transition-colors"
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept={tableUploadAccept()}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleUpload(file)
          e.target.value = ''
        }}
      />
    </div>
  )
}

function Message({ message, streaming }: { message: ChatMessage; streaming?: boolean }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-clay-500 to-clay-700 flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles className="w-3.5 h-3.5 text-white" />
        </div>
      )}

      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? 'bg-clay-600 text-white'
            : 'bg-white border border-slate-200/80 text-slate-700 shadow-sm'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm prose-slate max-w-none prose-p:my-1 prose-strong:text-slate-800">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {streaming && <span className="inline-block w-1.5 h-4 bg-clay-400 animate-pulse-soft ml-0.5 rounded-sm" />}
          </div>
        )}
      </div>
    </div>
  )
}

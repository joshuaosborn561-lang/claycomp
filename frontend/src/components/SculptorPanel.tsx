import { useEffect, useRef, useState } from 'react'
import { ArrowUp, FlaskConical, Hammer, Sparkles, Wand2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamSculptor } from '../api'
import { useSettings } from '../context/SettingsContext'
import type { ChatMessage, ColumnProposal, EnrichmentColumn, Enricher, LeadRecord } from '../types'

const STARTERS = [
  'What enrichments should I add?',
  'Add a column for nearest NFL team',
  'Help me write personalized openers',
  'What patterns do you see in my data?',
]

type Props = {
  records: LeadRecord[]
  columns: EnrichmentColumn[]
  enrichers: Enricher[]
  onAddColumn: (col: EnrichmentColumn) => void
  onSandbox: (col: EnrichmentColumn) => void
  onClose?: () => void
}

export default function SculptorPanel({
  records,
  columns,
  onAddColumn,
  onSandbox,
}: Props) {
  const { settings } = useSettings()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "I'm **Sculptor** — your enrichment co-pilot. Tell me what data you need and I'll propose columns, configure prompts, and help you test in sandbox before going live.",
    },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamBuffer, setStreamBuffer] = useState('')
  const [pendingProposals, setPendingProposals] = useState<ColumnProposal[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer, pendingProposals])

  const proposalToColumn = (p: ColumnProposal): EnrichmentColumn => ({
    id: `sculptor-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    enricherKey: p.enricher_key,
    label: p.label,
    columnName: p.column_name,
    customPrompt: p.custom_prompt,
    provider: settings.providerId,
    model: settings.model,
  })

  const send = async (text: string) => {
    if (!text.trim() || streaming) return

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text.trim() }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setStreaming(true)
    setStreamBuffer('')
    setPendingProposals([])

    let content = ''
    const proposals: ColumnProposal[] = []

    try {
      await streamSculptor(
        nextMessages,
        records,
        columns.map((c) => ({ enricherKey: c.enricherKey, label: c.label })),
        (event) => {
          if (event.type === 'token') {
            content += event.content as string
            setStreamBuffer(content)
          }
          if (event.type === 'proposal') {
            proposals.push(event.proposal as ColumnProposal)
            setPendingProposals([...proposals])
          }
          if (event.type === 'recommendations') {
            const recs = event.recommendations as { enricher_key: string; label: string; reason: string }[]
            for (const r of recs) {
              proposals.push({
                column_name: r.enricher_key,
                label: r.label,
                enricher_key: r.enricher_key,
                reasoning: r.reason,
              })
            }
            setPendingProposals([...proposals])
          }
        },
        settings,
      )

      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: content || 'Here are my suggestions.',
          proposals: proposals.length ? proposals : undefined,
        },
      ])
    } catch {
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: 'assistant', content: 'Something went wrong. Check your API key.' },
      ])
    } finally {
      setStreamBuffer('')
      setStreaming(false)
    }
  }

  return (
    <aside className="w-80 shrink-0 border-l border-slate-200/80 bg-white flex flex-col">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-clay-600 flex items-center justify-center">
          <Hammer className="w-3.5 h-3.5 text-white" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">Sculptor</h2>
          <p className="text-[10px] text-slate-400">Build enrichments with AI</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {messages.map((msg) => (
          <SculptorMessage key={msg.id} message={msg} />
        ))}

        {streamBuffer && (
          <SculptorMessage message={{ id: 'stream', role: 'assistant', content: streamBuffer }} streaming />
        )}

        {pendingProposals.length > 0 && (
          <div className="space-y-2 animate-fade-in">
            {pendingProposals.map((p, i) => {
              const col = proposalToColumn(p)
              return (
                <ProposalCard
                  key={`${p.column_name}-${i}`}
                  proposal={p}
                  onApply={() => onAddColumn(col)}
                  onSandbox={() => onSandbox(col)}
                />
              )
            })}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1.5">
          {STARTERS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-[10px] px-2 py-1 rounded-full border border-slate-200 text-slate-500 hover:border-clay-300 hover:text-clay-700"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="p-3 border-t border-slate-100">
        <div className="flex items-end gap-2 bg-slate-50 rounded-xl border border-slate-200 px-3 py-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Describe what to enrich…"
            rows={2}
            className="flex-1 resize-none bg-transparent text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || streaming}
            className="shrink-0 w-7 h-7 rounded-lg bg-clay-600 hover:bg-clay-700 disabled:opacity-30 text-white flex items-center justify-center"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2 text-center">
          Sandbox tests 3 rows · Apply adds column to table
        </p>
      </div>
    </aside>
  )
}

function SculptorMessage({ message, streaming }: { message: ChatMessage; streaming?: boolean }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-2 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <Wand2 className="w-3.5 h-3.5 text-clay-500 shrink-0 mt-1" />
      )}
      <div
        className={`max-w-[90%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser ? 'bg-clay-600 text-white' : 'bg-slate-50 text-slate-700 border border-slate-100'
        }`}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="prose prose-xs prose-slate max-w-none prose-p:my-1">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {streaming && <span className="inline-block w-1 h-3 bg-clay-400 animate-pulse-soft ml-0.5" />}
          </div>
        )}
      </div>
    </div>
  )
}

function ProposalCard({
  proposal,
  onApply,
  onSandbox,
}: {
  proposal: ColumnProposal
  onApply: () => void
  onSandbox: () => void
}) {
  return (
    <div className="rounded-xl border border-clay-200 bg-clay-50/50 p-3 space-y-2">
      <div className="flex items-start gap-2">
        <Sparkles className="w-3.5 h-3.5 text-clay-500 mt-0.5 shrink-0" />
        <div>
          <p className="text-xs font-semibold text-slate-800">{proposal.label}</p>
          {proposal.reasoning && (
            <p className="text-[10px] text-slate-500 mt-0.5">{proposal.reasoning}</p>
          )}
        </div>
      </div>
      <div className="flex gap-1.5">
        <button
          onClick={onSandbox}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-[10px] font-medium text-slate-600 hover:border-clay-300"
        >
          <FlaskConical className="w-3 h-3" />
          Sandbox
        </button>
        <button
          onClick={onApply}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg bg-clay-600 text-[10px] font-medium text-white hover:bg-clay-700"
        >
          Apply
        </button>
      </div>
    </div>
  )
}

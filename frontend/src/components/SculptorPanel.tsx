import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
  FlaskConical,
  Hammer,
  Layers,
  Mail,
  Sparkles,
  Wand2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamSculptor } from '../api'
import { useSettings } from '../context/SettingsContext'
import type {
  ChatMessage,
  ColumnProposal,
  DiagnosisIssue,
  EnrichmentColumn,
  LeadRecord,
  OutreachDraft,
  TableAnalysis,
  WorkflowProposal,
} from '../types'

const BUSINESS_CTX_KEY = 'claycomp-business-context'

const STARTERS = [
  'What enrichments should I add for cold outreach?',
  'Analyze my table — who should I prioritize?',
  'Build a full enrichment workflow for personalization',
  'Draft email openers for my top 3 leads',
  'Run sandbox: normalize names + find baseball teams',
  'Diagnose my table for issues',
]

type Props = {
  records: LeadRecord[]
  columns: EnrichmentColumn[]
  onAddColumn: (col: EnrichmentColumn) => void
  onApplyWorkflow: (steps: EnrichmentColumn[]) => void
  onSandbox: (col: EnrichmentColumn) => void
  onRecordsChange: (records: LeadRecord[]) => void
}

export default function SculptorPanel({
  records,
  columns,
  onAddColumn,
  onApplyWorkflow,
  onSandbox,
  onRecordsChange,
}: Props) {
  const { settings } = useSettings()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "I'm **Sculptor** — your GTM co-pilot. I can recommend enrichments, build workflows, analyze your data, draft outreach, run sandbox tests, and troubleshoot — like Clay.\n\nSet your **business context** below so I tailor everything to your ICP.",
    },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamBuffer, setStreamBuffer] = useState('')
  const [proposals, setProposals] = useState<ColumnProposal[]>([])
  const [workflows, setWorkflows] = useState<WorkflowProposal[]>([])
  const [analysis, setAnalysis] = useState<TableAnalysis | null>(null)
  const [drafts, setDrafts] = useState<OutreachDraft[]>([])
  const [diagnosis, setDiagnosis] = useState<DiagnosisIssue[]>([])
  const [costNote, setCostNote] = useState<string | null>(null)
  const [showContext, setShowContext] = useState(false)
  const [businessContext, setBusinessContext] = useState(() => localStorage.getItem(BUSINESS_CTX_KEY) || '')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    localStorage.setItem(BUSINESS_CTX_KEY, businessContext)
  }, [businessContext])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamBuffer, proposals, workflows, drafts, analysis])

  const proposalToColumn = (p: ColumnProposal): EnrichmentColumn => ({
    id: `sculptor-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    enricherKey: p.enricher_key,
    label: p.label,
    columnName: p.column_name,
    customPrompt: p.custom_prompt,
    provider: settings.providerId,
    model: settings.model,
  })

  const clearArtifacts = () => {
    setProposals([])
    setWorkflows([])
    setAnalysis(null)
    setDrafts([])
    setDiagnosis([])
    setCostNote(null)
  }

  const send = async (text: string) => {
    if (!text.trim() || streaming) return

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text.trim() }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setStreaming(true)
    setStreamBuffer('')
    clearArtifacts()

    let content = ''
    const newProposals: ColumnProposal[] = []

    try {
      const { records: updated } = await streamSculptor(
        nextMessages,
        records,
        columns.map((c) => ({
          enricherKey: c.enricherKey,
          label: c.label,
          customPrompt: c.customPrompt,
          columnName: c.columnName,
        })),
        (event) => {
          if (event.type === 'token') {
            content += event.content as string
            setStreamBuffer(content)
          }
          if (event.type === 'proposal') {
            const p = event.proposal as ColumnProposal
            newProposals.push(p)
            setProposals([...newProposals])
          }
          if (event.type === 'workflow') {
            const w = event.workflow as WorkflowProposal
            setWorkflows((prev) => [...prev, w])
          }
          if (event.type === 'analysis') {
            setAnalysis({ stats: event.stats as Record<string, unknown>, insights: event.insights as TableAnalysis['insights'] })
          }
          if (event.type === 'drafts') {
            setDrafts(event.drafts as OutreachDraft[])
          }
          if (event.type === 'diagnosis') {
            setDiagnosis(event.issues as DiagnosisIssue[])
          }
          if (event.type === 'cost_estimate') {
            const est = event.estimate as { estimated_ai_calls: number; sandbox_cost: number }
            setCostNote(`${event.summary} (~${est.estimated_ai_calls} AI calls, sandbox: ${est.sandbox_cost})`)
          }
          if (event.type === 'records') {
            onRecordsChange(event.records as LeadRecord[])
          }
          if (event.type === 'sandbox_complete') {
            content += `\n\n✓ Sandbox complete for **${event.label}** — check rows 1–3 in your table.`
            setStreamBuffer(content)
          }
        },
        settings,
        businessContext,
      )

      onRecordsChange(updated)
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: 'assistant', content: content || 'Done.', proposals: newProposals.length ? newProposals : undefined },
      ])
    } catch {
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: 'assistant', content: 'Something went wrong. Check your API key in Vercel settings.' },
      ])
    } finally {
      setStreamBuffer('')
      setStreaming(false)
    }
  }

  return (
    <aside className="w-96 shrink-0 border-l border-slate-200/80 bg-white flex flex-col">
      <div className="px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-clay-600 flex items-center justify-center">
            <Hammer className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold">Sculptor</h2>
            <p className="text-[10px] text-slate-400">GTM co-pilot · like Clay</p>
          </div>
        </div>
        <button
          onClick={() => setShowContext(!showContext)}
          className="mt-2 w-full flex items-center justify-between text-[10px] text-slate-500 hover:text-slate-700"
        >
          <span>Business context</span>
          {showContext ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        {showContext && (
          <textarea
            value={businessContext}
            onChange={(e) => setBusinessContext(e.target.value)}
            placeholder="We sell to VP Sales at B2B SaaS companies in the US. Our tone is casual and direct..."
            rows={3}
            className="mt-1.5 w-full text-[10px] px-2 py-1.5 rounded-lg border border-slate-200 resize-none focus:outline-none focus:ring-1 focus:ring-clay-300"
          />
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-3">
        {messages.map((msg) => (
          <SculptorMessage key={msg.id} message={msg} />
        ))}
        {streamBuffer && (
          <SculptorMessage message={{ id: 'stream', role: 'assistant', content: streamBuffer }} streaming />
        )}

        {analysis && (
          <ArtifactCard icon={<BarChart3 className="w-3.5 h-3.5" />} title="Table analysis">
            {analysis.insights?.insights?.map((ins, i) => (
              <p key={i} className="text-[10px] text-slate-600 mt-1">• {ins}</p>
            ))}
            {analysis.insights?.priority_segment && (
              <p className="text-[10px] text-clay-700 mt-2 font-medium">Priority: {analysis.insights.priority_segment}</p>
            )}
          </ArtifactCard>
        )}

        {workflows.map((w, i) => (
          <ArtifactCard key={i} icon={<Layers className="w-3.5 h-3.5" />} title={`Workflow: ${w.name}`}>
            <p className="text-[10px] text-slate-500">{w.reasoning}</p>
            <ul className="mt-1 space-y-0.5">
              {w.steps.map((s, j) => (
                <li key={j} className="text-[10px] text-slate-700">{j + 1}. {s.label || s.enricher_key}</li>
              ))}
            </ul>
            <button
              onClick={() => onApplyWorkflow(w.steps.map((s) => proposalToColumn({
                column_name: s.column_name || s.enricher_key,
                label: s.label,
                enricher_key: s.enricher_key,
                custom_prompt: s.custom_prompt,
              })))}
              className="mt-2 w-full py-1.5 rounded-lg bg-clay-600 text-white text-[10px] font-medium hover:bg-clay-700"
            >
              Apply all columns
            </button>
          </ArtifactCard>
        ))}

        {proposals.map((p, i) => (
          <ProposalCard
            key={`${p.column_name}-${i}`}
            proposal={p}
            onApply={() => onAddColumn(proposalToColumn(p))}
            onSandbox={() => onSandbox(proposalToColumn(p))}
          />
        ))}

        {drafts.map((d, i) => (
          <ArtifactCard key={i} icon={<Mail className="w-3.5 h-3.5" />} title={d.lead_name}>
            {d.subject && <p className="text-[10px] font-medium text-slate-700">Subject: {d.subject}</p>}
            <p className="text-[10px] text-slate-600 mt-1 italic">"{d.opener}"</p>
            {d.full_email && (
              <pre className="text-[9px] text-slate-500 mt-2 whitespace-pre-wrap font-sans">{d.full_email}</pre>
            )}
          </ArtifactCard>
        ))}

        {diagnosis.length > 0 && (
          <ArtifactCard icon={<Wand2 className="w-3.5 h-3.5" />} title="Diagnostics">
            {diagnosis.map((d, i) => (
              <div key={i} className="mt-1.5">
                <span className={`text-[9px] font-medium uppercase ${d.severity === 'error' ? 'text-red-500' : d.severity === 'warning' ? 'text-amber-500' : 'text-slate-400'}`}>
                  {d.severity}
                </span>
                <p className="text-[10px] text-slate-700">{d.issue}</p>
                <p className="text-[10px] text-slate-500">→ {d.fix}</p>
              </div>
            ))}
          </ArtifactCard>
        )}

        {costNote && (
          <p className="text-[10px] text-slate-500 bg-slate-50 rounded-lg px-2 py-1.5 border border-slate-100">{costNote}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1">
          {STARTERS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-[9px] px-2 py-1 rounded-full border border-slate-200 text-slate-500 hover:border-clay-300 hover:text-clay-700 text-left"
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
            placeholder="Ask Sculptor anything about your table…"
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
      </div>
    </aside>
  )
}

function ArtifactCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm animate-fade-in">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
        <span className="text-clay-500">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  )
}

function SculptorMessage({ message, streaming }: { message: ChatMessage; streaming?: boolean }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-2 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
      {!isUser && <Wand2 className="w-3.5 h-3.5 text-clay-500 shrink-0 mt-1" />}
      <div className={`max-w-[90%] rounded-xl px-3 py-2 text-xs leading-relaxed ${isUser ? 'bg-clay-600 text-white' : 'bg-slate-50 text-slate-700 border border-slate-100'}`}>
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

function ProposalCard({ proposal, onApply, onSandbox }: { proposal: ColumnProposal; onApply: () => void; onSandbox: () => void }) {
  return (
    <div className="rounded-xl border border-clay-200 bg-clay-50/50 p-3 space-y-2 animate-fade-in">
      <div className="flex items-start gap-2">
        <Sparkles className="w-3.5 h-3.5 text-clay-500 mt-0.5 shrink-0" />
        <div>
          <p className="text-xs font-semibold text-slate-800">{proposal.label}</p>
          {proposal.reasoning && <p className="text-[10px] text-slate-500 mt-0.5">{proposal.reasoning}</p>}
          {proposal.custom_prompt && (
            <p className="text-[9px] text-slate-400 mt-1 line-clamp-2">Prompt: {proposal.custom_prompt}</p>
          )}
        </div>
      </div>
      <div className="flex gap-1.5">
        <button onClick={onSandbox} className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-[10px] font-medium text-slate-600 hover:border-clay-300">
          <FlaskConical className="w-3 h-3" /> Sandbox
        </button>
        <button onClick={onApply} className="flex-1 py-1.5 rounded-lg bg-clay-600 text-[10px] font-medium text-white hover:bg-clay-700">
          Apply
        </button>
      </div>
    </div>
  )
}

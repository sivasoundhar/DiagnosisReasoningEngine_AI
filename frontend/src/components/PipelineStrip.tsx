import { useEffect, useState } from 'react'
import { Brain, CheckCircle2, ClipboardList, FlaskConical, ListChecks, ShieldAlert, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

const STEPS = [
  { key: 'symptom_analyzer', label: 'Symptom Analyzer', icon: Brain, desc: 'Matches symptoms against the medical knowledge base' },
  { key: 'lab_interpreter', label: 'Lab Interpreter', icon: FlaskConical, desc: 'Flags abnormal lab values' },
  { key: 'risk_assessor', label: 'Risk Assessor', icon: ShieldAlert, desc: 'Calculates severity score' },
  { key: 'recommender', label: 'Recommender', icon: ClipboardList, desc: 'Generates tests, treatments, follow-up' },
  { key: 'ai_reasoner', label: 'AI Reasoner', icon: Sparkles, desc: 'Independent LLM second opinion' },
  { key: 'ai_critic', label: 'AI Critic', icon: ListChecks, desc: 'LLM cross-check of the rule-based result' },
] as const

type StepStatus = 'idle' | 'active' | 'done'

interface PipelineStripProps {
  loading: boolean
  /** True once a result has been rendered (marks every step complete). */
  completed: boolean
}

/**
 * Visual of the 6-agent LangGraph pipeline (src/orchestrator/supervisor.py's
 * fixed order - 4 rule-based agents + the Day 12 AI Reasoner + the Day 13 AI
 * Critic). /analyze is one synchronous call - the backend doesn't stream
 * per-agent progress - so during `loading` this cycles through the steps as
 * a lightweight "working" animation rather than claiming to know the agents'
 * real-time state. Shows AI Reasoner/AI Critic as "Completed" once the
 * request finishes even if either degraded (no GROQ_API_KEY, or the call
 * failed) - same as how Lab Interpreter shows "Completed" even when no labs
 * were submitted; this strip reflects the pipeline stage running, not
 * whether that stage's optional output populated.
 */
export function PipelineStrip({ loading, completed }: PipelineStripProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    if (!loading) {
      setActiveIndex(0)
      return
    }
    const id = setInterval(() => {
      setActiveIndex((i) => (i + 1) % STEPS.length)
    }, 550)
    return () => clearInterval(id)
  }, [loading])

  function statusFor(index: number): StepStatus {
    if (completed) return 'done'
    if (loading) return index <= activeIndex ? (index === activeIndex ? 'active' : 'done') : 'idle'
    return 'idle'
  }

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-primary">
        <Brain className="size-4" />
        AI Reasoning Pipeline
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {STEPS.map((step, index) => {
          const status = statusFor(index)
          const Icon = step.icon
          return (
            <div
              key={step.key}
              className={cn(
                'rounded-lg border p-3 transition-colors',
                status === 'done' && 'border-emerald-200 bg-emerald-50',
                status === 'active' && 'border-primary/40 bg-accent',
                status === 'idle' && 'border-border bg-muted/40',
              )}
            >
              <div className="flex items-center justify-between">
                <div
                  className={cn(
                    'flex size-8 items-center justify-center rounded-full',
                    status === 'done' && 'bg-emerald-100 text-emerald-600',
                    status === 'active' && 'bg-primary/15 text-primary',
                    status === 'idle' && 'bg-muted text-muted-foreground',
                  )}
                >
                  {status === 'done' ? <CheckCircle2 className="size-4" /> : <Icon className={cn('size-4', status === 'active' && 'animate-pulse')} />}
                </div>
                <span className="text-xs font-medium text-muted-foreground">{index + 1}</span>
              </div>
              <p className="mt-2 text-sm font-medium leading-tight">{step.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {status === 'done' ? 'Completed' : status === 'active' ? 'Working…' : 'Queued'}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

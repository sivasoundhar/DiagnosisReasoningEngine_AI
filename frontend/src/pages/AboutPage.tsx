import { AlertTriangle, Brain, ClipboardList, FlaskConical, ListChecks, ShieldAlert, Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const PIPELINE_STEPS = [
  { icon: Brain, title: 'Symptom Analyzer', text: 'Scores candidate diagnoses by matching reported symptoms against the medical knowledge base (exact / partial / indirect matches).' },
  { icon: FlaskConical, title: 'Lab Interpreter', text: 'Flags abnormal lab values against normal/critical reference ranges and links them to supporting diagnoses.' },
  { icon: ShieldAlert, title: 'Risk Assessor', text: 'Combines age, comorbidities, diagnosis severity, and symptom red flags into a LOW–CRITICAL risk score.' },
  { icon: ClipboardList, title: 'Recommender', text: 'Produces tests, treatments, and a follow-up window, escalated by the assessed risk level.' },
  { icon: Sparkles, title: 'AI Reasoner', text: 'Independently asks an LLM (Groq) for its own differential, given only the original symptoms/labs/age/comorbidities — shown as a second opinion, never merged into the rule-based result above.' },
  { icon: ListChecks, title: 'AI Critic', text: 'The actual cross-check: shown the rule-based diagnosis/risk/recommendation and asked to critique it — flags concerns, missed considerations, and an agrees/partially agrees/disagrees verdict.' },
]

const TECH_STACK = [
  'FastAPI', 'LangGraph', 'Groq', 'Pydantic', 'SQLAlchemy', 'React 19', 'Vite', 'Tailwind CSS v4', 'shadcn/ui',
]

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-semibold">About</h1>
        <p className="text-sm text-muted-foreground">What this app is, and how it reasons about a patient.</p>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Diagnosis Reasoning Engine</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            A multi-agent clinical decision-support demo: six purpose-built agents run in a fixed
            LangGraph pipeline over a patient's symptoms, labs, age, and comorbidities, producing a
            ranked differential diagnosis, a risk assessment, a recommended workup, an independent
            AI second opinion, and an AI cross-check of that rule-based result — with the reasoning
            behind each step surfaced, not just the final answer.
          </p>
          <p>
            The first four agents' medical knowledge (symptom→diagnosis links, lab reference ranges,
            condition definitions, risk scoring weights) lives in versioned JSON files, not
            hardcoded logic — so that reasoning stays auditable and easy to extend. The last two
            agents are different on purpose: both are genuine LLM calls (Groq), kept clearly
            separate from the rule-based result rather than blended into it. AI Reasoner forms an
            independent opinion without seeing the rule-based result; AI Critic does the opposite —
            it IS shown that result and asked to critique it, which is the actual cross-verification
            step.
          </p>
          <p>
            Why two AI agents instead of one? Showing an LLM another system's answer before asking
            its opinion invites anchoring bias — models tend to just agree with what they're shown.
            So AI Reasoner stays blind, to give an honest comparison point; AI Critic stays informed,
            since a critique needs to see the specific choices it's critiquing. The trade-off: two
            model calls per analysis instead of one, so this step roughly doubles response time.
          </p>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>The 6-agent pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.title} className="flex gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-primary">
                <step.icon className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium">
                  {i + 1}. {step.title}
                </p>
                <p className="text-xs text-muted-foreground">{step.text}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Built with</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5">
            {TECH_STACK.map((t) => (
              <Badge key={t} variant="secondary">
                {t}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>Educational use only</AlertTitle>
        <AlertDescription>
          This system is for educational and research purposes only. It is not a medical device and
          must not be used for real clinical decisions. Always consult a qualified healthcare
          professional.
        </AlertDescription>
      </Alert>
    </div>
  )
}

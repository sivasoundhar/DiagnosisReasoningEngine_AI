# Diagnosis Reasoning Engine

A multi-agent clinical decision-support system. Four specialized [LangGraph](https://langchain-ai.github.io/langgraph/)
agents — Symptom Analyzer, Lab Interpreter, Risk Assessor, Recommender — deterministically reason
through a patient's symptoms, labs, age, and comorbidities to produce a ranked differential
diagnosis, a risk assessment, and a recommended workup, with the reasoning behind every step
surfaced explicitly rather than a black-box answer. Two more agents add genuine LLM reasoning on
top: the **AI Reasoning Agent** independently asks an LLM (Groq) for its own second opinion on the
same case, and the **AI Critic Agent** reviews the rule-based result itself and critiques it — the
actual cross-verification step. See [Why three kinds of reasoning](#why-three-kinds-of-reasoning)
below.

**Status:** Backend pipeline, full React UI, voice input, real-data validation, CI/CD, and Docker
are complete. Render deployment is a deliberate follow-up, not yet live.

## What it does

1. Enter (or speak) a patient's symptoms, age, comorbidities, and optional lab values
2. Four rule-based agents run in a fixed pipeline — Symptom Analyzer → Lab Interpreter → Risk
   Assessor → Recommender — then an LLM-based agent independently forms its own opinion on the same
   raw input, and a second LLM-based agent reviews and critiques the rule-based result specifically
3. Get back a ranked differential diagnosis, a LOW/MEDIUM/HIGH/CRITICAL risk score, recommended
   tests/treatments/follow-up, the reasoning chain behind each step, an AI second opinion flagged as
   agreeing or differing with the rule-based top diagnosis, and an AI cross-check with an
   agrees/partially agrees/disagrees verdict plus any concerns or missed considerations
4. Download a clean, print-ready clinical report; look up past analyses by patient; browse
   aggregated analytics across everything the instance has run

## Tech Stack

| Layer | Stack |
|---|---|
| Backend | FastAPI · LangGraph (6-agent `StateGraph` pipeline — 4 deterministic KB-driven agents + 2 LLM-based agents, see below) · SQLite · Pydantic |
| AI/LLM | Groq (`langchain-groq`), used by two agents (`ai_reasoner`, `ai_critic`) — see below |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 · shadcn/ui |
| Voice | Web Speech API (`SpeechRecognition` + `SpeechSynthesis`, browser-native) |
| Infra | Docker (multi-stage build) · GitHub Actions (CI now; Render deploy hook wired but inactive until Render is set up) |

## Why three kinds of reasoning

The four core agents are **deterministic and KB-driven on purpose** — symptom→diagnosis scoring,
lab reference-range interpretation, risk-factor point totals, and test/treatment recommendations
all come from the versioned JSON knowledge base in `src/knowledge/`, not a model call, so every
number the app produces traces back to an explicit rule (`docs/MEDICAL_KB.md`). That auditability
matters for a clinical tool and isn't going away.

But a rule-based pipeline alone doesn't *reason* the way "AI" usually implies, and the goal was a
genuinely intelligent second opinion, not only a scored lookup table. A 5th agent, `ai_reasoner`
(`src/agents/ai_reasoner.py`), closes that gap: it calls an LLM with the same raw
symptoms/labs/age/comorbidities the Symptom Analyzer sees — never the rule engine's output, so it
can't rubber-stamp an answer it was shown — and returns its own differential + narrative reasoning
as `ai_opinion` in the `/analyze` response.

A 6th agent, `ai_critic` (`src/agents/ai_critic.py`), exists for a different reason: showing two
independent opinions side by side isn't the same as *verifying* either one. AI Critic does the
opposite of AI Reasoner on purpose — it **is** shown the rule-based `diagnoses`/`risk_assessment`/
`recommendation` and asked to critique that specific result: an agrees/partially_agrees/disagrees
verdict, concrete concerns, and anything clinically relevant it thinks the rule engine missed,
returned as `ai_critique`. That's the actual cross-verification step.

### Why two LLM agents, not one

Asking one LLM agent to just "check" the rule-based result would look cheaper, but it conflates two
different jobs that need opposite inputs to do well:

- **AI Reasoner is blind on purpose** — it never sees the rule engine's answer, because showing an
  LLM another system's conclusion before asking its opinion invites **anchoring bias**: models tend
  to agree with whatever they're shown first. A "yes, looks right" from a reviewer that was primed
  with the answer is weak evidence. AI Reasoner exists to produce one genuinely uncontaminated data
  point to compare against.
- **AI Critic is informed on purpose** — it needs the rule-based result to say anything useful about
  it. An unprimed opinion structurally cannot say "that CT pulmonary angiogram recommendation looks
  excessive" or "you didn't weight the heart-disease comorbidity in the risk score" — it never saw
  those specific choices. Only an agent shown the actual output can critique the actual output.

This isn't hypothetical — it showed up in a live test run: AI Reasoner (blind) flagged generic red
flags ("severe respiratory distress, hypoxia"). AI Critic (informed), looking at the same case *plus*
the rule engine's actual risk score, caught something specific the rule-based Risk Assessor's fixed
point table didn't weight: *"the patient's heart disease comorbidity increases cardiac-complication
risk, which should factor into the differential and risk score."* AI Reasoner structurally couldn't
have produced that critique — it never saw the risk score to critique. One agent alone gives you
either an unaccountable second opinion or an agreeable, possibly-biased critique; together they
triangulate, which is the same blind-review + informed-critique split used in real LLM
evaluation/red-teaming work, not an invented pattern.

**The honest trade-off:** two Groq calls per analysis instead of one — roughly double the LLM
latency and API cost (~2.9s vs ~1.4s end-to-end in testing). Worth it for a decision-support tool
where catching anchoring bias matters more than shaving a second off response time; worth knowing
as a real cost line if this ever ran at production scale.

Both LLM agents are deliberately **supplementary, not authoritative**: if `GROQ_API_KEY` isn't set,
or a call fails, `ai_opinion`/`ai_critique` are simply `null` and the rest of the response is
unaffected — the auditable rule-based result is still a complete answer on its own, and neither LLM
agent's output ever feeds back into or alters it.

## Project Structure

```
src/
├── main.py                    # FastAPI app: /health, /analyze, /history/{id}, /feedback, /analytics
├── config.py                  # Pydantic Settings (reads .env)
├── database.py                 # SQLAlchemy models + session + auto-migration
├── models.py                    # Pydantic request/response schemas
├── agents/                       # 6 agents, each a 2-node LangGraph StateGraph
│   ├── base_agent.py               # Abstract BaseAgent all 6 inherit from
│   ├── symptom_analyzer.py           # Symptoms -> ranked differential diagnosis (rule-based)
│   ├── lab_interpreter.py             # Lab values -> abnormal-finding interpretations (rule-based)
│   ├── risk_assessor.py                # Age/comorbidities/diagnosis -> LOW..CRITICAL score (rule-based)
│   ├── recommender.py                   # Diagnosis + risk -> tests/treatments/follow-up (rule-based)
│   ├── ai_reasoner.py                    # Independent LLM (Groq) second opinion
│   └── ai_critic.py                       # LLM cross-check of the rule-based result
├── orchestrator/
│   └── supervisor.py            # Outer LangGraph wiring all 6 agents into one pipeline
└── knowledge/                   # The actual "brain" - versioned JSON, not hardcoded logic
    ├── medical_kb.py               # KnowledgeBase loader + symptom-synonym normalization
    ├── symptoms.json                 # 29 symptoms -> candidate diagnoses
    ├── labs.json                      # 15 labs, normal/critical ranges + interpretations
    ├── conditions.json                 # 21 condition definitions + tests/treatments/follow-up
    ├── risk_factors.json                # Scoring weights for the Risk Assessor
    └── recommendations.json              # Risk-level escalation rules for the Recommender

frontend/src/
├── pages/                      # Analyze, Patient History, Case Library, Analytics, Settings, About
├── components/                  # PatientForm, ResultsDisplay, PrintReport, MicButton, etc.
├── hooks/useSpeechRecognition.ts   # Web Speech API wrapper
└── lib/                         # Form state, fuzzy matching, date formatting, theme, etc.

scripts/
└── validate_ddxplus.py         # Real-data validation harness (see docs/TEST_RESULTS.md)

tests/                          # 109 pytest tests across all 6 agents + supervisor + API
docs/                           # ARCHITECTURE, API, MEDICAL_KB, TEST_RESULTS, DEPLOYMENT_NOTES
data/                           # DDXPlus dataset (gitignored - large; used for validation only)
```

## Setup

**Requirements:** Python 3.11+, Node 20+

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env

# Frontend
cd frontend
npm install
cp .env.example .env
```

## Running Locally

**Backend** (one terminal):
```bash
uvicorn src.main:app --reload
```
- http://localhost:8000/health → `{"status": "healthy"}`
- http://localhost:8000/docs → interactive API docs (Swagger UI)

**Frontend** (second terminal):
```bash
cd frontend
npm run dev
```
- http://localhost:5173

Both need to be running together — the frontend calls the backend via `VITE_API_URL`.

## Testing

```bash
pytest -v              # 109 tests: all 6 agents, supervisor, API endpoints (hermetic - no real Groq calls)
```

```bash
cd frontend
npm run build           # TypeScript check + production build
```

## Docker

```bash
docker build -t diagnosis-ai:latest .
docker run -p 8000:8000 --env-file .env diagnosis-ai:latest
```

Or the full stack (backend + dev-mode frontend) with docker-compose:
```bash
docker compose up --build
```

See `docs/DEPLOYMENT_NOTES.md` for image details and the Render deployment checklist.

## Real-Data Validation

Validated against 20 real patient cases from the [DDXPlus](https://github.com/mila-iqia/ddxplus)
dataset — one case per condition the app is designed to recognize. **75% plausible-or-better**
(35% exact top-diagnosis match, 40% correct diagnosis present in the differential). Full
methodology, per-case results, and honest failure analysis in `docs/TEST_RESULTS.md`. Reproduce
with `python scripts/validate_ddxplus.py`.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, agent pipeline, data flow
- [`docs/API.md`](docs/API.md) — endpoint reference with example requests/responses
- [`docs/MEDICAL_KB.md`](docs/MEDICAL_KB.md) — knowledge base structure and how to extend it
- [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md) — real-data validation results
- [`docs/DEPLOYMENT_NOTES.md`](docs/DEPLOYMENT_NOTES.md) — Docker details + Render checklist

## Disclaimer

Educational and research use only. Not a medical device. Not a substitute for professional medical
judgment. Always consult a qualified healthcare provider.

# Architecture

## Overview

```
┌─────────────┐      HTTP       ┌──────────────────────────────────────────────┐
│   React UI   │ ─────────────▶ │                FastAPI (src/main.py)          │
│ (frontend/)  │ ◀───────────── │  /analyze  /history  /feedback  /analytics    │
└─────────────┘      JSON       └───────────────────┬────────────────────────────┘
                                                      │
                                                      ▼
                                    ┌─────────────────────────────────┐
                                    │   DiagnosisSupervisor (Day 6)    │
                                    │   outer LangGraph StateGraph     │
                                    └─────────────────────────────────┘
                                                      │
        ┌─────────────────┬─────────────────┬────────┴────────┬─────────────────┐
        ▼                 ▼                 ▼                 ▼                 
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐        ┌────────────────┐        ┌────────────────┐
│Symptom Analyzer│ │Lab Interpreter│ │ Risk Assessor  │ │  Recommender   │──────▶│  AI Reasoner    │──────▶│  AI Critic      │
│  (Day 2)       │▶│  (Day 3)      │▶│  (Day 4)       │▶│  (Day 5)       │      │  (Day 12)        │      │  (Day 13)        │
│  rule-based    │ │  rule-based   │ │  rule-based    │ │  rule-based    │      │  LLM (Groq)       │      │  LLM (Groq)       │
└───────┬────────┘ └───────┬───────┘ └───────┬────────┘ └───────┬────────┘      └────────┬─────────┘      └────────┬─────────┘
        │                  │                 │                  │                        │                         │
        └──────────────────┴─────────────────┴──────────────────┘                        │                         │
                                     │                                                     │                         │
                                     ▼                                     reads ONLY original          reads the rule-based
                        ┌─────────────────────────┐                       symptoms/labs/age/            diagnoses/risk/
                        │   KnowledgeBase (JSON)   │                      comorbidities (never          recommendation +
                        │  symptoms · labs ·        │                     the 4 agents' output) ─┘      the original case,
                        │  conditions · risk_factors │                                                  critiques the result
                        │  · recommendations          │
                        └─────────────────────────┘
```

The first four agents are **deterministic and KB-driven** — every score traces back to an explicit
rule in `src/knowledge/*.json`, and the "reasoning" each produces is a human-readable string built
from those same rules, not a model's free-text output. The last two agents are the only LLM calls in
the codebase (see "AI Reasoner"/"AI Critic" below and the README's "Why three kinds of reasoning"),
and they're opposites on purpose: **AI Reasoner** only ever reads
`state["symptoms"/"labs"/"age"/"comorbidities"]` — the same raw input Symptom Analyzer started from
— never the other agents' output, so its opinion is genuinely independent rather than primed by the
rule engine's answer. **AI Critic** does the reverse: it's shown the rule-based result specifically
(`diagnoses`/`risk_assessment`/`recommendation`) and asked to critique it — that's the actual
cross-verification step, distinct from AI Reasoner just forming a second, unrelated opinion.

## The 4 rule-based agents

Each agent (`src/agents/*.py`) is its own small **2-node LangGraph `StateGraph`** — one node computes,
one node formats/ranks the result — a shape kept consistent across all 4 agents so wiring them into
the Day 6 supervisor was mechanical rather than a redesign.

### 1. Symptom Analyzer (`symptom_analyzer.py`)
**In:** `symptoms: list[str]` · **Out:** ranked `diagnoses` (top 5), `unknown_symptoms`

Looks up each symptom in `symptoms.json` (exact/partial/indirect match, weighted +50/+25/+10),
normalizes common synonyms/abbreviations first (`SOB` → `shortness of breath`, etc.), accumulates a
score per candidate diagnosis, and normalizes to a 0–100 confidence relative to the best possible
score for that many symptoms. Unrecognized symptoms are logged and skipped, never fatal — except an
**empty** symptom list, which raises `AgentError` (nothing downstream is meaningful without at least
one diagnosis).

### 2. Lab Interpreter (`lab_interpreter.py`)
**In:** `labs: dict[str, float]` · **Out:** `lab_interpretations` (status + confidence per lab),
`supporting_diagnoses`

Compares each value against `labs.json`'s normal/critical ranges. Values ≥10x the critical threshold
(or negative) are flagged `physiologically_implausible` rather than trusted as a real clinical
finding. Missing/empty labs is **not** an error (labs are optional) — returns an empty-but-successful
result.

### 3. Risk Assessor (`risk_assessor.py`)
**In:** `age`, `comorbidities`, `primary_diagnosis` (the Symptom Analyzer's top pick),
`severity_indicators` (the raw symptom list) · **Out:** `risk_level` (LOW/MEDIUM/HIGH/CRITICAL),
`score`, `score_breakdown`, `likely_complications`

Sums points from age brackets, comorbidities, diagnosis severity, and symptom-based severity
indicators (`risk_factors.json`), all fully auditable via `score_breakdown`. Missing/invalid age
falls back to a default with a warning logged, never a crash.

### 4. Recommender (`recommender.py`)
**In:** `diagnoses` (the full differential, not just #1), `risk_level`, `age` · **Out:** `tests`,
`treatments`, `follow_up`

Merges each diagnosis's baseline workup from `conditions.json` (order-preserving dedupe across
multiple diagnoses), escalates by risk level (`recommendations.json` — e.g. CRITICAL adds ICU
admission + continuous monitoring), and adds age-specific tests for patients ≥65. Unknown diagnoses
fall back to a generic workup rather than an empty recommendation.

## The AI Reasoner (Day 12)

**In:** `symptoms`, `labs`, `age`, `comorbidities` — the *original* patient input only · **Out:**
`ai_diagnoses` (up to 5, name/confidence/reasoning), `ai_summary`, `red_flags`, `model_used`

The one agent in this codebase that calls an LLM. Its own 2-node graph (`build_case_summary` →
`call_llm`) turns the structured input into a short plain-English case description, then calls
Groq (`ChatGroq.with_structured_output`, see `src/agents/ai_reasoner.py`) with a system prompt
asking for an independent differential + reasoning, parsed straight into a Pydantic schema so the
output shape is guaranteed even though the content itself is now genuinely LLM-generated, not
rule-derived. The LLM client is dependency-injected (`AIReasonerAgent(llm=..., model_name=...)`) —
built from `settings.groq_api_key`/`groq_model` by the supervisor's default construction
(`default_groq_llm()`), or a fake in every test, so the test suite never touches the network.
`llm=None` (no `GROQ_API_KEY` configured) is a first-class, explicit "unavailable" state, not an
implicit failure.

## The AI Critic (Day 13)

**In:** `symptoms`/`labs`/`age`/`comorbidities` (the original case, for context) **plus**
`diagnoses`/`risk_assessment`/`recommendation` (the rule engine's actual result) · **Out:**
`assessment` (`agrees`/`partially_agrees`/`disagrees`), `concerns`, `missed_considerations`,
`narrative`, `model_used`

The cross-verification step, and the mirror image of AI Reasoner: same shape (its own 2-node graph,
`build_review_context` → `call_llm`, `ChatGroq.with_structured_output`, dependency-injected `llm`,
`llm=None` → explicit `AgentError`), but the opposite input contract. Its `review_context` string
explicitly includes the rule-based differential, risk score/reasoning, and recommended
tests/treatments — the LLM is asked to critique *that specific result*, not to independently guess
again. `assessment` is normalized (case/whitespace-trimmed) and defaults to `partially_agrees` if the
model returns something outside the three valid values, so a malformed response never silently
becomes an unrecognized string in the API response.

**Why this needs to be a separate agent from AI Reasoner, not a flag on it:** the two need opposite
inputs to do their jobs. AI Reasoner's independence is only meaningful *because* it never sees the
rule-based result (an LLM shown another system's answer and asked "do you agree?" tends to just
agree — anchoring bias). AI Critic's critique is only meaningful *because* it does see the result —
it can't say "that CT pulmonary angiogram recommendation looks excessive" without knowing that was
recommended. One agent trying to do both jobs would have to choose which input to withhold, which
defeats one purpose or the other. Concrete evidence this isn't just a design nicety: in a live run,
AI Reasoner (blind) produced generic red flags, while AI Critic (informed), given the same case plus
the actual `risk_assessment`, caught that the rule-based Risk Assessor's fixed point table didn't
weight the patient's heart-disease comorbidity toward cardiac-complication risk — a critique that
requires seeing the score to make. See the README's "Why two LLM agents, not one" for the full
reasoning, including the latency/cost trade-off of running two Groq calls per analysis.

## The Supervisor (Day 6, extended Day 12 and Day 13)

`src/orchestrator/supervisor.py`'s `DiagnosisSupervisor` is an **outer** LangGraph `StateGraph`
treating each agent as one node, wired in a fixed sequential order: Symptom Analyzer → Lab
Interpreter → Risk Assessor → Recommender → AI Reasoner → AI Critic. `SupervisorState` (a
`TypedDict`) threads input (`symptoms`/`labs`/`age`/`comorbidities`) through to output
(`diagnoses`/`lab_interpretations`/`risk_assessment`/`recommendation`/`ai_opinion`/`ai_critique`),
plus an `errors` list for diagnostics. State wiring between agents:
- Risk Assessor's `primary_diagnosis` = Symptom Analyzer's top-ranked diagnosis name
- Risk Assessor's `severity_indicators` = the raw reported symptoms
- Recommender's `risk_level` = Risk Assessor's output; `diagnoses` = the full differential
- **AI Reasoner receives none of the above** — only the original `symptoms`/`labs`/`age`/
  `comorbidities` state that was present before Symptom Analyzer ever ran (`_run_ai_reasoner`
  rebuilds its input from `state.get(...)` on those four keys specifically, not from `**state`), so
  its opinion can't be primed by the rule engine's answer
- **AI Critic receives the opposite** — the original four keys *plus* `diagnoses`/
  `risk_assessment`/`recommendation` (`_run_ai_critic` explicitly passes all seven), because its
  entire job is reviewing that specific result, not forming an unprimed opinion

By default the supervisor builds one shared Groq client (`default_groq_llm()`) and passes it to both
AI Reasoner and AI Critic — one API key, one client, two agents using it for different prompts — but
each accepts its own `llm=`/`ai_reasoner=`/`ai_critic=` override for tests.

**Two-tier error handling:** if the Symptom Analyzer itself fails (e.g. empty symptoms), the whole
pipeline aborts with `SupervisorError` — nothing downstream is meaningful without at least one
diagnosis. If Lab Interpreter/Risk Assessor/Recommender/AI Reasoner/AI Critic fail individually, each
is caught, logged into `state["errors"]`, and degrades to an empty/`None` result so the pipeline
still completes (e.g. missing labs, or no `GROQ_API_KEY`, never breaks a run).

The supervisor and its `KnowledgeBase` are built **once** at FastAPI startup (`lifespan`, see
`main.py`) — not per-request — so the KB JSON and all 7 compiled LangGraph graphs (6 agents + the
outer supervisor graph) are loaded a single time for the app's life.

## Database (`src/database.py`)

SQLite, one table (`patient_records`): every `/analyze` call is persisted (symptoms, labs, age,
comorbidities, the full `DiagnosisOutput` as JSON, optional `patient_name`) so `/history/{id}` can
look it up, `/feedback` can attach a clinician's actual diagnosis, and `/analytics` can aggregate
across everything stored. `init_db()` runs an idempotent `ADD COLUMN` migration pass on startup for
columns added after the table already existed on disk (`create_all()` only creates missing *tables*,
not missing *columns*).

## Frontend (`frontend/src/`)

Single-page React app, no router library — `App.tsx` holds `activeView` state and switches between 6
pages (`lib/views.ts`'s `AppView` union) rendered inside `AppShell` (sidebar nav, collapses to a top
bar on mobile). Two contexts wrap the app: `ThemeProvider` (light/dark, localStorage-backed) and
`AnalysisFormProvider` (lifts the Analyze form's state above the page level so Case Library can hand
a preset patient to it across a navigation).

- **`pages/DiagnosisPage.tsx`** — the main flow: `PatientForm` → `analyzeDiagnosis()` API call →
  `ResultsDisplay` (which itself renders both the on-screen dashboard cards *and* `PrintReport`, a
  separate plain-document layout that only shows up via `print:hidden`/`print:block` when printing —
  not the same cards with chrome hidden).
- **`pages/PatientHistoryPage.tsx`** — search by patient ID (backed by `/history/{id}`), reuses
  `ResultsDisplay` for each past entry.
- **`pages/AnalyticsPage.tsx`** — stat tiles + two labeled bar-list breakdowns (risk distribution,
  top diagnoses), backed by `/analytics`.
- **`hooks/useSpeechRecognition.ts`** — wraps the Web Speech API for voice input (Day 9). Uses
  `continuous: false` per underlying session (the reliable mode — Chrome's `continuous: true` has
  long-standing bugs where it silently stops delivering results) with its own auto-restart-on-end
  logic to still support natural pauses between spoken symptoms.

## Request lifecycle: `POST /analyze`

1. `PatientInput` validated by Pydantic (symptoms non-empty, age 0–120) — a `RequestValidationError`
   here becomes a 400, not FastAPI's default 422.
2. `patient.model_dump()` → `DiagnosisSupervisor.run()` → the 6-agent pipeline above.
3. An `AgentError`/`SupervisorError` from the pipeline becomes a 500 with a generic message (the real
   exception is logged server-side, never echoed to the client).
4. On success: a `PatientRecord` row is written (patient_id — auto-generated in `PT-YYYYMMDD-XXXXXX`
   format if not supplied — patient_name, symptoms, labs, age, comorbidities, the full result JSON),
   and the `DiagnosisOutput` is returned.

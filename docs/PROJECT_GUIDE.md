# Project Guide — Diagnosis Reasoning Engine

This is the "read this first, understand everything, run it yourself" document. If you're coming
back to this project after a break, handing it to someone else, or just want the full picture in
one place — this is it.

## Contents

1. [5-minute quickstart](#1-5-minute-quickstart)
2. [What is this project?](#2-what-is-this-project)
3. [Aim / why this exists](#3-aim--why-this-exists)
4. [Who it's for](#4-who-its-for--the-use-case)
5. [How it actually works](#5-how-it-actually-works)
6. [A worked example, start to finish](#6-a-worked-example-start-to-finish)
7. [Where the data comes from](#7-where-the-data-comes-from)
8. [How to run it locally (full detail)](#8-how-to-run-it-locally-full-detail)
9. [Feature tour](#9-feature-tour)
10. [Testing](#10-testing)
11. [Common tasks](#11-common-tasks)
12. [Glossary](#12-glossary)
13. [Where everything lives](#13-where-everything-lives)
14. [Troubleshooting](#14-troubleshooting)
15. [Status at a glance](#15-status-at-a-glance)

---

## 1. 5-minute quickstart

Skip the explanations for now — this is the fastest path to seeing it actually work.

```bash
# Terminal 1 — backend
python -m venv .venv && .venv\Scripts\activate      # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env                                # Windows; use cp on macOS/Linux
uvicorn src.main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
copy .env.example .env
npm run dev
```
Open **http://localhost:5173**, click **"Autofill Example"**, click **"Analyze Patient"**. You
should see a ranked diagnosis, a risk score, and recommendations within about a second. If that
worked, the whole thing works — everything else in this doc is detail. If something didn't work,
jump straight to [§14 Troubleshooting](#14-troubleshooting).

---

## 2. What is this project?

A **multi-agent clinical decision-support system**. You give it a patient's symptoms, age,
comorbidities, and (optionally) lab results — by typing or by voice — and six specialized agents
reason through the case (four deterministic rule-based agents in sequence, plus two independent
LLM-based agents) to produce:

- A **ranked differential diagnosis** (the most likely conditions, with confidence scores)
- A **risk assessment** (LOW / MEDIUM / HIGH / CRITICAL, with a points breakdown you can audit)
- A **recommended workup** (tests to run, treatments to consider, when to follow up)
- The **reasoning behind every one of those steps**, in plain English — not a black-box answer

Think of it as a structured "second opinion" tool that shows its work at every step, rather than a
chatbot that just gives you an answer.

## 3. Aim / why this exists

Two goals:

1. **A genuinely useful clinical reasoning tool** — fast triage support, especially valuable
   somewhere with limited specialist access or a high patient load, where a second, consistent,
   always-explainable opinion has real value.
2. **A portfolio-quality demonstration of multi-agent AI system design** — not "call an LLM and
   hope," but a deliberately engineered pipeline: deterministic, data-driven agents; a real
   knowledge base instead of hardcoded logic; measured accuracy against real clinical data;
   full-stack polish (voice input, printable reports, analytics); and production concerns (Docker,
   CI/CD, real test coverage) taken seriously, not bolted on at the end.

## 4. Who it's for / the use case

- **A clinician or triage nurse** entering a patient's presentation and getting a fast, structured,
  explainable differential + risk read — hands-free via voice if they're mid-examination.
- **A patient history keeper** — every analysis is saved, searchable by patient, and a clinician
  can attach their own confirmed diagnosis afterward (feedback loop, for eventually measuring how
  often the system agreed with reality).
- **Anyone studying multi-agent AI system design** — this codebase is a clean, small, fully-tested
  reference for "how do you actually structure a multi-step reasoning pipeline with LangGraph
  without reaching for an LLM you don't need yet."

**This is explicitly not a medical device.** Educational/research use only — every page in the app
and every generated report says so. It's not a substitute for professional medical judgment.

## 5. How it actually works

```
You (type or speak) → symptoms, age, comorbidities, labs
        │
        ▼
┌─────────────────┐   "What could this be?"
│ Symptom Analyzer │   Matches symptoms against a knowledge base, ranks candidate diagnoses
└────────┬─────────┘
         ▼
┌─────────────────┐   "What do the labs say?"
│ Lab Interpreter  │   Flags abnormal values against normal/critical reference ranges
└────────┬─────────┘
         ▼
┌─────────────────┐   "How urgent is this?"
│  Risk Assessor   │   Scores age + comorbidities + diagnosis severity + red-flag symptoms
└────────┬─────────┘
         ▼
┌─────────────────┐   "What should happen next?"
│   Recommender    │   Tests, treatments, follow-up window — escalated by the risk level
└────────┬─────────┘
         ▼
┌─────────────────┐   "What's an independent AI take on this same case?"
│  AI Reasoner     │   Calls an LLM (Groq) with the ORIGINAL symptoms/labs/age/comorbidities
│                  │   only — never the 4 steps above — for a genuinely independent 2nd opinion
└────────┬─────────┘
         ▼
┌─────────────────┐   "Does the rule-based result actually hold up?"
│  AI Critic       │   Shown the rule engine's OWN diagnosis/risk/recommendation and asked to
│                  │   critique it — agrees / partially agrees / disagrees, plus any concerns
└────────┬─────────┘
         ▼
   Ranked diagnosis + risk score + action plan + full reasoning trail +
   AI second opinion + AI cross-check verdict
```

And how that fits into the rest of the system:

```
┌────────────┐   HTTP/JSON   ┌─────────────────────┐   in-process   ┌───────────────────┐
│  React UI   │ ────────────▶│  FastAPI (src/main)  │──────────────▶│  6-agent pipeline   │
│ (frontend/) │◀──────────── │  /analyze /history … │◀────────────── │  (diagram above)     │
└────────────┘               └──────────┬───────────┘                └─────────┬─────────┘
                                         │                                       │ ai_reasoner +
                                         ▼                                       ▼ ai_critic only
                                 ┌───────────────┐                    ┌───────────────────┐
                                 │ SQLite (data/) │                    │  Groq API (LLM)     │
                                 └───────────────┘                    └───────────────────┘
                                 every analysis saved for /history, /analytics
```

**Four of the six agents call no LLM.** Their logic is deterministic and driven by JSON files in
`src/knowledge/` — symptom→diagnosis links, lab reference ranges, condition definitions, risk
scoring weights. This was a deliberate choice: the reasoning behind a risk score or a diagnosis
match is always traceable to a specific rule, not a model's guess at an explanation. `LangGraph` is
used to *orchestrate* all 6 steps as a pipeline (each agent is its own small 2-node graph; an outer
graph wires all 6 together).

**The last two agents, AI Reasoner and AI Critic, are genuine LLM calls.** They do opposite jobs
on purpose, which is what makes the pair meaningful rather than redundant:
- **AI Reasoner** reads only the original patient input, independently produces its own differential
  + reasoning via Groq, and is surfaced as `ai_opinion` — clearly separate from the rule engine's
  `diagnoses`, so a clinician sees both and can judge where they agree or diverge.
- **AI Critic** is shown the rule engine's *own* `diagnoses`/`risk_assessment`/`recommendation` and
  asked to review it specifically — an agrees/partially-agrees/disagrees verdict, concrete concerns,
  and anything it thinks the rule engine missed, surfaced as `ai_critique`. This is the actual
  cross-verification step: AI Reasoner alone just gives you two unrelated opinions to eyeball, AI
  Critic is what actually checks the rule-based result's work.

**Why not just one LLM agent that does both?** Because the two jobs need opposite inputs. Showing an
LLM another system's answer before asking its opinion invites *anchoring bias* — models tend to just
agree with what they're shown. So AI Reasoner stays blind, to be a genuinely uncontaminated
comparison point. But a blind opinion can't critique specific choices it never saw ("that CT
pulmonary angiogram recommendation looks excessive" requires knowing it was recommended) — so AI
Critic stays informed. In a live test, AI Reasoner (blind) gave generic red flags, while AI Critic
(informed) caught something AI Reasoner structurally couldn't: that the rule-based Risk Assessor's
point table didn't weight the patient's heart-disease comorbidity toward cardiac risk. One agent
alone gives you either an unaccountable second opinion or an agreeable, possibly-biased critique —
together they triangulate. The real cost of that: two Groq calls per analysis instead of one,
roughly doubling LLM latency (~2.9s vs ~1.4s observed) and API usage — a reasonable trade for a
decision-support tool, but a real line item if this ran at scale.

If `GROQ_API_KEY` isn't set, both `ai_opinion` and `ai_critique` are simply `null` and everything
else still works. Full technical detail in `docs/ARCHITECTURE.md`.

## 6. A worked example, start to finish

Concrete, not abstract — this is a real call against the real app, so you know exactly what to
expect when you run it yourself.

**You send** (via the UI, or `POST /analyze` directly):
```json
{
  "symptoms": ["fever", "cough", "shortness of breath"],
  "age": 62,
  "labs": {"WBC": 12.5, "CRP": 8.5},
  "comorbidities": ["diabetes"]
}
```

**You get back**, roughly a second later:
- **Top diagnosis:** Pneumonia, 100% confidence — *"fever (strong match) + cough (strong match) +
  shortness of breath (strong match)"*
- **Risk:** CRITICAL, 80 points — *"age 62 + comorbidity: diabetes + diagnosis: Pneumonia + severity
  indicator: shortness of breath = CRITICAL (80 points)"*
- **Recommended:** Chest X-ray, blood culture, CBC, and 10 more tests; antibiotics, oxygen therapy,
  and more; follow-up: *"Continuous ICU monitoring required."*
- Plus the full reasoning chain, and both abnormal labs (WBC and CRP, both flagged ELEVATED) with
  their own plain-English interpretations.
- **AI second opinion** (if `GROQ_API_KEY` is configured): an independently-generated differential
  from Groq, e.g. *"Pneumonia (78%) — fever, cough, and SOB together strongly suggest bacterial
  pneumonia, especially with an elevated WBC/CRP pattern,"* plus a short clinical summary and any
  red flags it noticed — shown next to, not merged into, the rule-based diagnoses above.
- **AI cross-check** (same requirement): a verdict on the rule-based result *itself* — e.g.
  *"agrees — the top diagnosis is well-supported and the risk classification is appropriate"* — plus
  any concerns and anything it thinks was missed (e.g. *"consider a D-dimer to formally rule out PE
  given the shortness of breath"*).

Every rule-based number above is *computed*, not looked up from a table of canned answers — change any input
(drop "diabetes," change the age, remove a symptom) and the score, risk level, and recommendations
all shift accordingly, traceably. The full response shape (every field explained) is in
`docs/API.md`.

## 7. Where the data comes from

Two completely separate data sources, doing two different jobs — don't mix them up:

### The knowledge base (`src/knowledge/*.json`) — what the app *reasons with*
Hand-authored, versioned JSON: 29 symptoms, 15 labs, 21 conditions, risk-scoring weights,
recommendation rules. This is what every `/analyze` call actually uses. Full structure documented
in `docs/MEDICAL_KB.md`.

### DDXPlus (`data/`) — what the app was *validated against*
[**DDXPlus**](https://github.com/mila-iqia/ddxplus) ([paper](https://arxiv.org/abs/2205.09148)) is
a large synthetic dataset of patient cases (structured symptoms, differential diagnoses,
ground-truth pathology) built for exactly this kind of diagnosis-reasoning research — used here as
the real-data validation source.

- It's **gitignored** (85MB+ CSVs) — not needed to run the app day-to-day, only to reproduce the
  validation.
- `scripts/validate_ddxplus.py` maps a curated subset of DDXPlus's 223 structured clinical-intake
  codes onto this app's 29-symptom vocabulary (documented explicitly in the script and in
  `docs/TEST_RESULTS.md` — DDXPlus doesn't store symptoms as plain English, so this mapping is real
  engineering, not a formality).
- **Result: 75% plausible-or-better** across 20 real cases (one per condition this app knows about).
  Full breakdown and honest failure analysis in `docs/TEST_RESULTS.md`.

If you ever want to re-run or extend the validation, that dataset needs to already be sitting in
`data/release_test_patients/`, `data/release_evidences.json`, and `data/release_conditions.json` —
download DDXPlus separately if it's not already there.

## 8. How to run it locally (full detail)

**You need:** Python 3.11+, Node 20+. (Docker is optional — see below.)

### Backend
```bash
cd DiagnosisReasoningEngine_AI
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux

pip install -r requirements.txt
cp .env.example .env                # defaults work out of the box, nothing to fill in required

uvicorn src.main:app --reload
```
Wait for `Uvicorn running on http://0.0.0.0:8000`. Check it worked:
```bash
curl http://localhost:8000/health   # {"status": "healthy"}
```
Interactive API docs: http://localhost:8000/docs

### Frontend (second terminal, backend must already be running)
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Wait for `Local: http://localhost:5173/`, then open that in your browser. **Both need to be running
at the same time** — the frontend calls the backend over HTTP.

### Or, the whole thing via Docker
```bash
docker compose up --build
```
Same two URLs (`:8000` backend, `:5173` frontend). See `docs/DEPLOYMENT_NOTES.md` for image details
(it's a lean 474MB multi-stage build) and what's still needed before this could go live on Render
(deliberately not done yet).

## 9. Feature tour

- **Analyze Patient** — the main flow: symptoms (typed or **voice input**), age, comorbidities,
  labs, optional name/ID → full 6-agent pipeline → ranked diagnosis, risk, recommendations,
  reasoning chain, and (if `GROQ_API_KEY` is set) an **AI second opinion** panel shown next to an
  **AI cross-check** panel — the former flagged as agreeing or differing with the top rule-based
  diagnosis, the latter showing an agrees/partially-agrees/disagrees verdict on the rule-based
  result itself, plus any concerns or missed considerations.
  **Download Report** produces a clean, printable PDF via the browser's native print dialog — not
  the on-screen dashboard cards, a purpose-built plain document layout.
- **Patient History** — look up past analyses by patient ID, a "recently analyzed on this device"
  shortcut list, and a feedback form to attach a clinician's actual confirmed diagnosis.
- **Case Library** — 5 hand-built sample patients (not from DDXPlus — see `docs/TEST_RESULTS.md`
  for why that mapping is kept separate) covering the full risk spectrum, one click loads them into
  the Analyze form.
- **Analytics** — aggregate stats across everything this instance has analyzed: totals, risk-level
  distribution, most common diagnoses, feedback coverage.
- **Settings** — light/dark theme, a default lab panel (which labs auto-appear on a new analysis),
  and voice input language (accent) selection.
- **About** — the disclaimer, tech stack, and pipeline explainer, in-app.
- **Voice input** — click the mic, say your symptoms, they get parsed into tags automatically.
  Handles natural pauses between symptoms and re-ranks the speech engine's guesses against known
  medical vocabulary (so a misheard word has a real chance of self-correcting). Needs a real
  microphone to test.

## 10. Testing

```bash
pytest -v              # 109 tests: all 6 agents, the supervisor, every API endpoint
```
The AI Reasoner's and AI Critic's tests (and every other test that builds a `DiagnosisSupervisor`)
never hit the real Groq API — a fake LLM/agent is injected instead, and `tests/conftest.py`
force-clears `GROQ_API_KEY` for the whole test session so the suite stays hermetic even if your
local `.env` has a real key in it.
```bash
cd frontend && npm run build     # TypeScript check + production build (no separate frontend test suite yet)
```
```bash
python scripts/validate_ddxplus.py   # Re-run the real-data validation (needs DDXPlus in data/)
```

## 11. Common tasks

**Add a new symptom, lab, or condition** — edit the relevant JSON file in `src/knowledge/`, restart
the backend (the KB loads once at startup), run `pytest -v` to confirm nothing broke. No agent code
changes needed. Full field-by-field structure in `docs/MEDICAL_KB.md`.

**Reset the local database** — stop the backend, delete `data/database.db`, restart it. A fresh
empty one is created automatically (`init_db()` runs on every startup).

**Run just one agent's tests** — `pytest tests/test_symptom_agent.py -v` (swap the filename for
`lab_agent`, `risk_agent`, `recommender_agent`, `ai_reasoner_agent`, `ai_critic_agent`, `supervisor`,
`api`, or `health`).

**Turn on the AI second opinion and cross-check** — get a free Groq API key at console.groq.com, set
`GROQ_API_KEY` in `.env`, restart the backend (`--reload` doesn't watch `.env` — a full process
restart is needed). No code change needed; `ai_opinion` and `ai_critique` both go from `null` to
populated on the next `/analyze` call.

**See exactly what a request/response looks like without opening the UI** — the app's own
interactive docs at http://localhost:8000/docs let you fire requests and see real responses
directly, or use `curl` (examples throughout `docs/API.md`).

## 12. Glossary

| Term | Plain-English meaning |
|---|---|
| **Agent** | One focused piece of reasoning logic (e.g. "figure out the risk level") — 4 of the 6 are narrow deterministic functions, 2 (AI Reasoner, AI Critic) are genuine LLM calls |
| **Differential diagnosis** | A ranked list of possible conditions that could explain a set of symptoms, most-likely first — the actual medical term for "what could this be" |
| **LangGraph** | A library for wiring multiple steps (nodes) into a pipeline (a graph) with shared state flowing between them — used here for orchestration; two nodes (AI Reasoner, AI Critic) also do real generation |
| **Knowledge base (KB)** | The JSON files in `src/knowledge/` that the 4 rule-based agents' logic is driven by — the "facts" the system reasons with, editable without touching code |
| **Supervisor** | The outer LangGraph that runs all 6 agents in order and passes each one's output into the next (`src/orchestrator/supervisor.py`) |
| **AI opinion** | The AI Reasoner's independent LLM-generated differential + reasoning, returned as `ai_opinion` — supplementary to, never a replacement for, the rule-based `diagnoses` |
| **AI critique** | The AI Critic's cross-check of the rule-based result, returned as `ai_critique` — an agrees/partially_agrees/disagrees verdict plus concerns/missed considerations, the opposite input contract from `ai_opinion` (this agent IS shown the rule-based result) |
| **DDXPlus** | The real-world-adjacent dataset used to validate this app's accuracy (see §7) — not something the app uses at runtime, only for testing |
| **Risk score / risk level** | A points total (see `docs/MEDICAL_KB.md`) mapped to LOW/MEDIUM/HIGH/CRITICAL — how urgently a patient needs attention |
| **Confidence** | 0–100%, how strongly a diagnosis's symptoms matched the knowledge base — not a probability of being correct, a match-strength score |
| **Plausible** (in `docs/TEST_RESULTS.md`) | The correct answer was somewhere in the top-5 differential, just not ranked #1 |

## 13. Where everything lives

| I want to... | Look at |
|---|---|
| Understand the system design in depth | `docs/ARCHITECTURE.md` |
| See every API endpoint with real examples | `docs/API.md` |
| Understand/extend the knowledge base | `docs/MEDICAL_KB.md` |
| See validation methodology + results | `docs/TEST_RESULTS.md` |
| Deploy this somewhere | `docs/DEPLOYMENT_NOTES.md` |

## 14. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `pip install` fails with SSL/certificate errors | Corporate proxy or a machine with cert issues — retry with `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r requirements.txt` |
| Backend won't start, port 8000 already in use | Something else is already running there — `uvicorn src.main:app --reload --port 8001` and update `VITE_API_URL` in `frontend/.env` to match |
| Frontend shows blank page / network errors | Backend isn't running, or `VITE_API_URL` doesn't match where it's actually running — check `frontend/.env` |
| `docker build`/`docker run` fails immediately | Docker Desktop's daemon isn't running — start Docker Desktop, wait for it to fully start, retry |
| Log lines like `"Unrecognized severity indicator 'X' - skipping"` | Expected, harmless — the Risk Assessor only recognizes specific red-flag symptoms (SOB, chest pain, confusion, hypotension); anything else is logged and skipped, not a bug |
| Voice input mis-hears words, or doesn't pick up speech at all | See the detailed checklist below — this is a known, extensively-debugged rough edge |
| `GROQ_API_KEY` not set | Both AI agents degrade gracefully — `ai_opinion` and `ai_critique` are `null` in every `/analyze` response, everything else works normally. Set a real key in `.env` and restart to enable them (see §11) |
| AI second opinion / cross-check never appears even with `GROQ_API_KEY` set | Check backend logs for an `ai_reasoner` or `ai_critic` error (bad key, network, rate limit) — it's logged and recorded but never crashes the request. Remember `--reload` doesn't watch `.env` — a full restart is needed after changing the key |
| History/Analytics reset after a Docker/Render restart | SQLite's file lives inside the container — see the persistence note in `docs/DEPLOYMENT_NOTES.md` |

**Voice input checklist**, in order:
1. Website mic permission granted? (browser will prompt on first use)
2. OS-level mic permission for your specific browser? (Windows: Settings → Privacy & security → Microphone)
3. Correct input device selected? (check for a Bluetooth device silently taking priority over a wired one)
4. Are you speaking *immediately* after clicking? (short listening window before it decides nothing's coming)
5. Try a different accent/locale under Settings → Voice Input Language
6. Still wrong after all of that → likely a genuine speech-recognition accuracy limit (Chrome sends
   audio to Google's cloud model — this app biases the result toward known medical vocabulary but
   can't fix the underlying model's hearing).

## 15. Status at a glance

Backend pipeline, full React UI, voice input, and real-data validation are complete and tested.
CI/CD and Docker are finished and verified. **`git push` and Render deployment are intentionally
not done yet** — next steps whenever you're ready to pick them back up.

The AI Reasoning Agent adds a genuine, independent LLM (Groq) second opinion. The AI Critic Agent
adds real cross-verification: it IS shown the rule-based `diagnoses`/`risk_assessment`/
`recommendation` and asked to critique that specific result, returning `ai_critique` (an
agrees/partially_agrees/disagrees verdict, concerns, missed considerations). 109 backend tests
pass, all hermetic (no test hits the real Groq API). Both AI agents require a `GROQ_API_KEY` to
produce output at runtime — without one, `ai_opinion` and `ai_critique` are both `null` and every
other feature is unaffected. Live-verified end-to-end with a real Groq key against the running app.

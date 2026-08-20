# API Reference

Base URL (local): `http://localhost:8000`. Interactive Swagger docs at `/docs` while the server is
running. All request/response examples below are real output from the actual endpoints, not
hand-written samples.

## `GET /health`

Health check, used by Docker's `HEALTHCHECK` and load balancers.

**Response `200`:**
```json
{"status": "healthy"}
```

---

## `POST /analyze`

Runs the full 6-agent pipeline on a patient and persists the result.

**Request body** (`PatientInput`):

| Field | Type | Required | Notes |
|---|---|---|---|
| `symptoms` | `string[]` | ✅ | At least 1. Free text — unrecognized terms are skipped gracefully, not rejected. |
| `age` | `int` | ✅ | 0–120 |
| `labs` | `{[name]: number}` | — | Optional. See `docs/MEDICAL_KB.md` for the 15 known lab names/units. |
| `comorbidities` | `string[]` | — | Optional. Known: `diabetes`, `heart disease`, `cancer`, `kidney disease`, `liver disease`. |
| `patient_id` | `string \| null` | — | Optional. Auto-generated (`PT-YYYYMMDD-XXXXXX`) if omitted. |
| `patient_name` | `string \| null` | — | Optional display name, echoed back and stored for history/reports. |

```json
{
  "symptoms": ["fever", "cough", "shortness of breath"],
  "age": 62,
  "labs": {"WBC": 12.5, "CRP": 8.5},
  "comorbidities": ["diabetes"]
}
```

**Response `200`** (`DiagnosisOutput`):
```json
{
  "patient_id": "PT-20260812-FED773",
  "patient_name": null,
  "diagnoses": [
    {
      "name": "Pneumonia",
      "confidence": 100.0,
      "reasoning": "Pneumonia (100.0): fever (strong match) + cough (strong match) + shortness of breath (strong match)"
    },
    {
      "name": "Influenza",
      "confidence": 33.3,
      "reasoning": "Influenza (33.3): fever (strong match)"
    }
  ],
  "lab_interpretations": [
    {
      "lab_name": "WBC",
      "value": 12.5,
      "status": "ELEVATED",
      "interpretation": "Elevated WBC suggests active infection or inflammation",
      "confidence": 90.0
    }
  ],
  "risk_assessment": {
    "risk_level": "CRITICAL",
    "score": 80,
    "reasoning": "age 62 + comorbidity: diabetes + diagnosis: Pneumonia + severity indicator: shortness of breath = CRITICAL (80 points)",
    "likely_complications": ["Immediate hospitalization recommended", "Risk of multi-organ failure", "Continuous monitoring required"]
  },
  "recommendation": {
    "tests": ["Chest X-ray", "Blood culture", "CBC"],
    "treatments": ["Antibiotic (amoxicillin or azithromycin)", "Supportive care"],
    "follow_up": "Continuous ICU monitoring required."
  },
  "ai_opinion": {
    "diagnoses": [
      {
        "name": "Pneumonia",
        "confidence": 78.0,
        "reasoning": "Fever, cough, and shortness of breath together, with an elevated WBC/CRP pattern, strongly suggest bacterial pneumonia."
      }
    ],
    "summary": "Presentation is most consistent with community-acquired pneumonia; consider chest imaging and blood cultures before starting antibiotics.",
    "red_flags": ["shortness of breath"],
    "model": "llama-3.3-70b-versatile"
  },
  "ai_critique": {
    "assessment": "agrees",
    "concerns": [],
    "missed_considerations": ["Consider D-dimer/CT pulmonary angiogram given SOB, to formally rule out PE alongside pneumonia"],
    "narrative": "The top diagnosis of pneumonia is well-supported by the symptom cluster and elevated inflammatory markers, and the CRITICAL risk classification with ICU-level recommendations is appropriate given the patient's age and comorbidity. The differential could be marginally broadened to formally exclude pulmonary embolism.",
    "model": "llama-3.3-70b-versatile"
  },
  "analyzed_at": "2026-08-12T09:49:39.302784Z"
}
```
*(`diagnoses`/`recommendation` arrays truncated above for readability — see the pipeline docs in
`docs/ARCHITECTURE.md` for full field meaning.)*

**`ai_opinion`** is the AI Reasoning Agent's independent LLM (Groq) second opinion — built
from the same raw `symptoms`/`labs`/`age`/`comorbidities` as the request, never from the rule
engine's own `diagnoses`/`risk_assessment`/`recommendation`, so it's a genuinely separate take, not
a rephrasing of the rule-based result.

**`ai_critique`** is the AI Critic Agent's cross-check — the opposite input contract from
`ai_opinion`: it IS shown the rule-based `diagnoses`/`risk_assessment`/`recommendation` and asked to
review that specific result. `assessment` is always one of `agrees`/`partially_agrees`/`disagrees`;
`concerns` and `missed_considerations` are empty arrays (not omitted) when the model has none to
report.

Both `ai_opinion` and `ai_critique` are **`null`** whenever `GROQ_API_KEY` isn't configured on the
server, or the corresponding Groq call failed for this request — the rest of the response is
unaffected either way, so treat both as always-optional in client code.

**`400`** — validation failure (missing/empty `symptoms`, `age` out of range, etc.):
```json
{
  "error": "bad_request",
  "detail": "[{'type': 'too_short', 'loc': ('body', 'symptoms'), 'msg': 'List should have at least 1 item after validation, not 0', ...}]"
}
```

**`500`** — the pipeline itself failed unexpectedly. The real exception is logged server-side only;
the client gets a generic message (`"Diagnosis pipeline failed. Please try again."`).

---

## `GET /history/{patient_id}`

Past analyses for a patient, most recent first.

**Response `200`** (`HistoryEntry[]`):
```json
[
  {
    "id": 1,
    "patient_id": "demo-1",
    "patient_name": "Jane Doe",
    "created_at": "2026-08-12T09:54:31.371314",
    "symptoms": ["fever", "cough"],
    "age": 45,
    "comorbidities": [],
    "result": { "...": "full DiagnosisOutput, same shape as /analyze's response" }
  }
]
```

**`404`** — no records for that `patient_id`:
```json
{"error": "not_found", "detail": "404: No history found for patient_id 'no-such-patient'."}
```

---

## `POST /feedback`

Attaches a clinician's actual diagnosis / free-text notes to a patient's **latest** analysis.

**Request body** (`FeedbackInput`):
```json
{
  "patient_id": "demo-1",
  "actual_diagnosis": "Pneumonia",
  "feedback_text": "Confirmed on chest X-ray."
}
```
`feedback_text` is optional.

**Response `200`:**
```json
{"status": "success", "message": "Feedback recorded."}
```

**`404`** — no record found for that `patient_id`.

---

## `GET /analytics`

Aggregated stats across every analysis stored on this instance (not per-patient). Computed on
demand from every stored record — no separate stats table to keep in sync.

**Response `200`** (`AnalyticsSummary`):
```json
{
  "total_analyses": 1,
  "unique_patients": 1,
  "risk_level_distribution": {"MEDIUM": 1},
  "top_diagnoses": [{"name": "Pneumonia", "count": 1}],
  "records_with_feedback": 1,
  "feedback_coverage_pct": 100.0,
  "first_analysis_at": "2026-08-12T09:54:31.371314",
  "last_analysis_at": "2026-08-12T09:54:31.371314"
}
```
Returns zeroed fields (not an error) when the table is empty. `top_diagnoses` is capped at the top 5
by frequency of appearing as the #1 (highest-confidence) diagnosis.

---

## Error shape

Every error response (400/404/500) uses the same `ErrorResponse` shape:
```json
{"error": "bad_request | not_found | internal_error", "detail": "human-readable detail or null"}
```

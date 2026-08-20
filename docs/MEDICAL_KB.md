# Medical Knowledge Base

Every agent's reasoning is driven by the JSON files in `src/knowledge/`, loaded once at startup by
`KnowledgeBase` (`medical_kb.py`) — **not hardcoded logic**. This is deliberate: adding a symptom,
adjusting a lab range, or changing a risk weight is a data edit, not a code change, and every number
the app produces can be traced back to a specific line in one of these files.

## `symptoms.json` — 29 symptoms → candidate diagnoses

```json
{
  "fever": [
    {"name": "Pneumonia", "match": "exact"},
    {"name": "Influenza", "match": "exact"},
    {"name": "URTI", "match": "partial"}
  ]
}
```
`match` strength drives the Symptom Analyzer's scoring: `exact` = +50, `partial` = +25, `indirect` =
+10 points toward that diagnosis. `medical_kb.py` also has `SYMPTOM_SYNONYMS` (~26 common
abbreviations, e.g. `SOB` → `shortness of breath`) applied before lookup, and
`normalize_symptom()`/`get_diagnoses_for_symptom()` are the actual lookup path every agent (and the
Day 10 validation script) goes through.

## `labs.json` — 15 labs, reference ranges + interpretations

```json
{
  "unit": "10^9/L",
  "normal_min": 4.5, "normal_max": 11.0,
  "critical_low": 2.0, "critical_high": 30.0,
  "interpretation": {
    "low": "Leukopenia - reduced infection-fighting capacity, possible bone marrow suppression",
    "elevated": "Elevated WBC suggests active infection or inflammation",
    "critical": "Severely abnormal WBC - possible sepsis or hematologic emergency"
  },
  "linked_diagnoses": ["Pneumonia", "Bronchitis"]
}
```
The 15 known labs: `WBC`, `CRP`, `glucose`, `hemoglobin`, `troponin`, `d_dimer`, `creatinine`, `BUN`,
`sodium`, `potassium`, `platelets`, `BNP`, `procalcitonin`, `AST`, `ALT`. A value ≥10x the critical
threshold (or negative) is flagged `physiologically_implausible` by the Lab Interpreter rather than
trusted as real — treated as a likely data-entry error.

## `conditions.json` — 21 condition definitions

```json
{
  "description": "Infection that inflames air sacs in one or both lungs.",
  "severity": "moderate",
  "typical_symptoms": ["fever", "cough", "shortness of breath", "chills", "sputum production"],
  "risk_factors": ["age > 65", "smoking", "chronic lung disease", "weakened immune system"],
  "tests": ["Chest X-ray", "Blood culture", "CBC", "Basic metabolic panel", "Sputum culture", "Pulse oximetry"],
  "treatments": ["Antibiotic (amoxicillin or azithromycin)", "Supportive care", "Monitor O2 saturation"],
  "follow_up": "48-72 hours to assess treatment response"
}
```
`severity` (`mild`/`moderate`/`severe`/`critical`) feeds the Risk Assessor's diagnosis-severity
points. `tests`/`treatments`/`follow_up` are the Recommender's per-condition baseline, before
risk-level escalation. **20 of these 21 condition names exactly match a DDXPlus pathology name**
(chosen deliberately so Day 10 validation lines up without renaming) — only `Sepsis` doesn't, added
later for a specific test scenario.

## `risk_factors.json` — Risk Assessor scoring weights

| Section | What it drives |
|---|---|
| `age_brackets` | Points by age range (0-30=0, 31-60=10, 61-75=20, 76+=30) |
| `comorbidity_points` | diabetes=15, heart disease=25, cancer=30, kidney disease=20, liver disease=25 |
| `severity_points` | Points by diagnosis `severity` (mild=10, moderate=30, severe=50, critical=70) |
| `severity_indicator_points` | Points for specific reported symptoms (SOB=15, chest pain=20, confusion=25, hypotension=30) |
| `risk_level_thresholds` | Score → LOW (0-25) / MEDIUM (26-50) / HIGH (51-75) / CRITICAL (76+) |
| `complications_by_level` | Text shown per risk level |

Every point contributing to a score is recorded in the Risk Assessor's `score_breakdown` — nothing
is a mystery number.

## `recommendations.json` — Recommender escalation rules

```json
{
  "LOW": "Follow up in 1-2 weeks if symptoms are not improving.",
  "MEDIUM": "Recheck labs and symptoms within 48 hours.",
  "HIGH": "Daily monitoring required while hospitalized.",
  "CRITICAL": "Continuous ICU monitoring required."
}
```
(`follow_up_by_risk_level`, shown above) **overrides** any single diagnosis's own `follow_up` when
they conflict — risk level dominates a disease's natural-history baseline (e.g. a HIGH-risk
pneumonia patient needs daily inpatient monitoring, not the disease's baseline 48–72h recheck). Also
holds `risk_level_actions` (tests/treatments added per risk tier), `elderly_age_threshold` (65) +
`elderly_additional_tests`, `unknown_diagnosis_workup` (generic fallback), and
`test_rationale`/`treatment_rationale` (shared explanation text, not duplicated per condition).

## Extending the KB

Adding a new symptom, lab, or condition is a JSON edit in the relevant file — no agent code changes
needed as long as the shape matches the examples above. After editing:
1. Restart the backend (KB is loaded once at startup, not per-request)
2. Run `pytest -v` — the existing test suite (87 tests) will catch anything the change breaks
3. If it's a new condition worth validating against real data, `scripts/validate_ddxplus.py` can
   pick it up automatically if the name also exists as a DDXPlus pathology (see `docs/TEST_RESULTS.md`)

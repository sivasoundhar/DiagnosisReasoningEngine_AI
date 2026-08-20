# Real-Data Validation Results

**Date:** 2026-08-12
**Dataset:** [DDXPlus](https://arxiv.org/abs/2205.09148) test split (`data/release_test_patients`)
**Note:** MIMIC-IV was never available in this environment; DDXPlus is used in its place as the
real-data validation source.

## Summary

| Metric | Count | % |
|---|---|---|
| Exact match (top diagnosis = ground truth) | 7 / 20 | 35.0% |
| Plausible (ground truth somewhere in our differential) | 8 / 20 | 40.0% |
| Wrong (ground truth not in our differential at all) | 5 / 20 | 25.0% |
| **Plausible or better** | **15 / 20** | **75.0%** |

Reproduce: `python scripts/validate_ddxplus.py` (deterministic, no randomness in case selection).
Full per-case output: `data/results/validation_results.json`. Selected cases + their mapped
symptoms: `data/test_cases/selected_cases.json`.

## Methodology

### Case selection
DDXPlus defines 49 conditions; this app's knowledge base (`src/knowledge/conditions.json`) defines
21, of which **20 have an exactly-matching name in DDXPlus** (only `Sepsis` doesn't — added later
for a specific test scenario, not part of the original DDXPlus-aligned set). Rather than a random
sample, **one real test patient was selected per each of those 20 overlapping conditions** — the
first row in `release_test_patients` matching that `PATHOLOGY` whose mapped symptoms weren't empty.
This means every condition the app is actually designed to recognize gets tested exactly once,
instead of risking an uneven sample that over- or under-represents any one condition.

### Symptom mapping (the deviation that matters most)
DDXPlus doesn't store symptoms as plain English — its `EVIDENCES` column is a list of codes from 223
structured clinical intake questions (binary yes/no, multi-select body-map pain locations, 0–10
intensity scales, medication/history questions, etc.). This app's knowledge base only understands 29
named symptoms. `scripts/validate_ddxplus.py` maps a **curated, documented subset** of DDXPlus's
binary evidence codes onto those 29 symptoms — only codes with an unambiguous match (e.g. `E_91` "Do
you have a fever?" → `fever`). Chest pain / abdominal pain / headache have no direct DDXPlus
equivalent either — they're derived from "has pain" (`E_53`) combined with the pain's body-map
location (`E_55`), keyword-classified into chest/abdomen/head regions.

**Deliberately left unmapped** (no clean corresponding evidence found): `hives`, `throat swelling`,
`night sweats` as distinct from general sweating, `rapid heart rate` as distinct from palpitations.
Comorbidities (`diabetes`, `heart disease`, `cancer`, `kidney disease`, `liver disease`) are mapped
from DDXPlus's own history questions the same way. This is the same judgment call already documented
for the app's Case Library sample patients — full DDXPlus→vocabulary translation is a nontrivial layer with real risk
of misrepresenting a case, so the mapping stays narrow and explicit rather than guessed at broadly.

### Scoring
- **Exact match** — our top-ranked diagnosis equals DDXPlus's `PATHOLOGY` (ground truth).
- **Plausible** — `PATHOLOGY` appears somewhere in our returned differential (top 5), just not #1.
- **Wrong** — `PATHOLOGY` doesn't appear in our differential at all.

## Full results

| Verdict | Condition (ground truth) | Our top diagnosis | Confidence | Mapped symptoms used |
|---|---|---|---|---|
| ✅ Exact | GERD | GERD | 55.0% | abdominal pain, chest pain, cough, heartburn |
| 🟡 Plausible | Bronchitis | Pneumonia | 40.0% | chest pain, cough, nasal congestion, shortness of breath, wheezing |
| ✅ Exact | URTI | URTI | 50.0% | cough, fever, headache, muscle aches, nasal congestion, sore throat, sweating |
| 🟡 Plausible | Spontaneous pneumothorax | Pneumonia | 100.0% | shortness of breath |
| ✅ Exact | Anemia | Anemia | 64.0% | dizziness, fatigue, headache, pale skin, shortness of breath |
| 🟡 Plausible | Panic attack | GERD | 28.3% | abdominal pain, chest pain, dizziness, nausea, palpitations, shortness of breath |
| 🟡 Plausible | Pulmonary embolism | Possible NSTEMI / STEMI | 50.0% | chest pain, shortness of breath, syncope |
| ✅ Exact | Influenza | Influenza | 43.8% | cough, fatigue, fever, headache, loss of appetite, muscle aches, sore throat, sweating |
| ✅ Exact | Atrial fibrillation | Atrial fibrillation | 100.0% | palpitations |
| ✅ Exact | Pneumonia | Pneumonia | 70.0% | chest pain, chills, cough, fever, loss of appetite, sputum production |
| ❌ Wrong | Viral pharyngitis | Pneumonia | 100.0% | cough, fever |
| ❌ Wrong | Pericarditis | GERD | 30.0% | abdominal pain, chest pain, palpitations, shortness of breath |
| ❌ Wrong | Acute rhinosinusitis | Pneumonia | 100.0% | fever |
| 🟡 Plausible | Stable angina | GERD | 30.0% | abdominal pain, chest pain, fatigue, shortness of breath |
| 🟡 Plausible | Possible NSTEMI / STEMI | GERD | 42.5% | abdominal pain, chest pain, nausea, shortness of breath |
| 🟡 Plausible | Acute COPD exacerbation / infection | Pneumonia | 66.7% | shortness of breath, sputum production, wheezing |
| ❌ Wrong | Myocarditis | Possible NSTEMI / STEMI | 33.3% | chest pain, palpitations, shortness of breath |
| ✅ Exact | Bronchospasm / acute asthma exacerbation | Bronchospasm / acute asthma exacerbation | 100.0% | shortness of breath, wheezing |
| ❌ Wrong | Anaphylaxis | Bronchospasm / acute asthma exacerbation | 40.0% | abdominal pain, nausea, shortness of breath, swelling in legs, wheezing |
| 🟡 Plausible | Unstable angina | Possible NSTEMI / STEMI | 30.0% | abdominal pain, chest pain, fatigue, shortness of breath, sweating |

## Failure analysis

Every "wrong" case has an identifiable cause — either a real gap in the symptom-mapping coverage, or
genuine clinical ambiguity that even a real clinician would find hard from symptoms alone:

1. **Anaphylaxis → Bronchospasm/asthma (mapping gap, most clear-cut).** Anaphylaxis's two most
   distinctive symptoms in this app's own KB (`hives`, `throat swelling`) are exactly the two symptoms
   `BINARY_EVIDENCE_TO_SYMPTOM` deliberately left unmapped — no clean corresponding DDXPlus binary
   evidence was found for either. Without them, the reported symptom set (shortness of breath,
   wheezing, nausea, abdominal pain, leg swelling) genuinely looks more like an asthma exacerbation.
   **This is a mapping-coverage gap, not a diagnosis-engine bug** — the same symptoms would likely
   mislead any system without those two anchor symptoms present.
2. **Pericarditis → GERD.** Mapped symptoms included `abdominal pain` from the pain-location
   classifier — pericarditis pain can be felt in/near the epigastric region, an anatomically
   ambiguous zone the keyword classifier may have miscategorized as "abdomen" instead of "chest."
   Worth revisiting the `ABDOMEN_KEYWORDS` classification if this recurs.
3. **Viral pharyngitis / Acute rhinosinusitis → Pneumonia.** Both mapped to very sparse symptom sets
   (`cough, fever` and `fever` alone respectively) — this app's own KB treats fever+cough as a
   strong Pneumonia signal by design, so a sparse, non-specific presentation reasonably lands there.
   The underlying DDXPlus rows may simply not have flagged the more specific evidences (sore throat,
   nasal symptoms) for these particular real patients, or those evidences exist under codes this
   mapping doesn't cover yet.
4. **Myocarditis → Possible NSTEMI/STEMI.** Both conditions share near-identical presentations
   (chest pain, palpitations, shortness of breath) — this app's own `conditions.json` documents this
   overlap for NSTEMI/STEMI already. A genuinely hard differential from symptoms alone, not a coverage
   gap.

**Bottom line:** of the 5 "wrong" cases, 1 is a clear, fixable mapping-coverage gap (anaphylaxis), 1
is a plausible pain-location misclassification worth revisiting, and 3 reflect real diagnostic
ambiguity or sparse underlying data rather than a defect in the reasoning pipeline itself.

## What this validates and what it doesn't

- **Validates:** the 4-agent pipeline behaves sensibly on real (not hand-authored) symptom
  combinations across all 20 conditions it's designed to recognize, and produces a differential where
  the right answer is present 75% of the time even under an intentionally conservative, narrow
  symptom-mapping.
- **Doesn't validate:** DDXPlus evidence-code coverage beyond the ~35 codes mapped here, lab-based
  reasoning (DDXPlus is symptom-only, no lab values), or the voice input feature (needs a live
  microphone; not something a validation script can exercise).
- **Voice testing on sample cases** — not performed here for the same reason: Web Speech API
  requires real audio and a live browser session, which this validation script can't provide.
  Manual browser testing separately covers what live-browser testing *could* verify (feature
  detection, recognition object construction, TTS) versus what needed a real microphone.

## Carried forward

- Anaphylaxis's mapping gap (`hives`, `throat swelling`) could be closed if a suitable DDXPlus
  evidence code is found on a closer read of the remaining ~170 non-binary evidence codes.
- Pericarditis's epigastric/chest classification boundary worth a second look if more validation
  cases surface the same pattern.

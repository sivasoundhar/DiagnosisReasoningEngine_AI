"""Validate the diagnosis pipeline against 20 real patient cases from
the DDXPlus dataset (data/release_test_patients) - MIMIC-IV was never
available in this environment, so DDXPlus is used as the substitute
real-data validation source.

DDXPlus's own "EVIDENCES" column is a list of fine-grained clinical intake
codes (223 possible questions - body-map pain locations, symptom-character
scales, medication history, etc.), not plain-English symptom names. This
script maps a curated, documented subset of those codes onto this app's own
29-symptom / 5-comorbidity vocabulary (src/knowledge/symptoms.json). Only
codes with a clear, defensible 1:1 (or pain+location -> named-pain-symptom)
correspondence are mapped; everything else is deliberately left unmapped
rather than guessed at - see MAPPING NOTES below for exactly what's covered
and what isn't.

One test patient is selected per condition name that exists in BOTH this
app's src/knowledge/conditions.json (21 entries) and DDXPlus's 49
conditions (20 overlap - only "Sepsis" doesn't, added later for a specific
test scenario) - not a random sample, so results reflect exactly one real
case per condition this app is actually designed to recognize, and every
condition it knows about gets covered exactly once.

Run: python scripts/validate_ddxplus.py
"""
from __future__ import annotations

import ast
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.knowledge.medical_kb import KnowledgeBase  # noqa: E402
from src.orchestrator.supervisor import DiagnosisSupervisor  # noqa: E402

DATA_DIR = ROOT / "data"
TEST_PATIENTS_CSV = DATA_DIR / "release_test_patients" / "release_test_patients"
EVIDENCES_JSON = DATA_DIR / "release_evidences.json"
CONDITIONS_JSON = ROOT / "src" / "knowledge" / "conditions.json"
RESULTS_DIR = DATA_DIR / "results"
TEST_CASES_DIR = DATA_DIR / "test_cases"
TEST_RESULTS_MD = ROOT / "docs" / "TEST_RESULTS.md"

RANDOM_SEED = 42
NUM_CASES = 20

# --- MAPPING NOTES ------------------------------------------------------
# Binary DDXPlus evidence code -> this app's symptom name. Only codes whose
# question text is an unambiguous match to one of our 29 known symptoms.
BINARY_EVIDENCE_TO_SYMPTOM: dict[str, str] = {
    "E_91": "fever",
    "E_201": "cough",
    "E_66": "shortness of breath",
    "E_64": "shortness of breath",
    "E_97": "sore throat",
    "E_181": "nasal congestion",
    "E_77": "sputum production",
    "E_214": "wheezing",
    "E_112": "wheezing",
    "E_88": "fatigue",
    "E_89": "fatigue",
    "E_76": "dizziness",
    "E_82": "dizziness",
    "E_155": "palpitations",
    "E_148": "nausea",
    "E_211": "vomiting",
    "E_166": "vomiting",
    "E_51": "diarrhea",
    "E_173": "heartburn",
    "E_50": "sweating",
    "E_94": "chills",
    "E_144": "muscle aches",
    "E_161": "loss of appetite",
    "E_32": "loss of appetite",
    "E_174": "loss of appetite",
    "E_151": "swelling in legs",  # DDXPlus's E_151 is general body swelling, not leg-specific - closest available match
    "E_154": "pale skin",
    "E_159": "syncope",
}
# Deliberately NOT mapped (no clean corresponding binary evidence found):
# hives, throat swelling, night sweats (vs. general sweating), rapid heart
# rate as distinct from palpitations.

# Binary DDXPlus evidence code -> this app's comorbidity name.
BINARY_EVIDENCE_TO_COMORBIDITY: dict[str, str] = {
    "E_69": "diabetes",
    "E_105": "heart disease",
    "E_106": "heart disease",
    "E_139": "heart disease",
    "E_22": "heart disease",
    "E_34": "cancer",
    "E_37": "cancer",
    "E_113": "kidney disease",
    "E_126": "liver disease",
}

# Pain location (E_55's V_-code) English label keywords -> named pain
# symptom. E_53 ("pain related to your reason for consulting") + a location
# in one of these sets is how chest/abdominal/head pain get derived, since
# DDXPlus has no direct "do you have chest pain" binary - it's pain +
# body-map location instead.
CHEST_KEYWORDS = ("chest",)
ABDOMEN_KEYWORDS = ("belly", "epigastric", "flank", "hypochondrium", "iliac fossa")
HEAD_KEYWORDS = ("forehead", "temple", "occiput", "top of the head", "back of head")


def load_location_categories() -> tuple[set[str], set[str], set[str]]:
    """V_-code -> category, derived from E_55's value_meaning English labels."""
    evidences = json.loads(EVIDENCES_JSON.read_text(encoding="utf-8"))
    value_meaning = evidences["E_55"]["value_meaning"]
    chest, abdomen, head = set(), set(), set()
    for v_code, meaning in value_meaning.items():
        label = meaning.get("en", "").lower()
        if any(k in label for k in CHEST_KEYWORDS):
            chest.add(v_code)
        elif any(k in label for k in ABDOMEN_KEYWORDS):
            abdomen.add(v_code)
        elif any(k in label for k in HEAD_KEYWORDS):
            head.add(v_code)
    return chest, abdomen, head


def parse_evidence_list(raw: str) -> list[str]:
    """The EVIDENCES column is a Python-list-literal string, e.g.
    "['E_53', 'E_54_@_V_112', 'E_55_@_V_29']" - safe to literal_eval."""
    return ast.literal_eval(raw)


def map_evidences(
    evidence_codes: list[str], chest_locs: set[str], abdomen_locs: set[str], head_locs: set[str]
) -> tuple[list[str], list[str]]:
    """Returns (symptoms, comorbidities) mapped from one patient's raw evidence list."""
    plain_codes = set()
    location_values: list[str] = []
    has_pain = False

    for entry in evidence_codes:
        if entry == "E_53":
            has_pain = True
        if "_@_" in entry:
            code, value = entry.split("_@_", 1)
            if code == "E_55":
                location_values.append(value)
        else:
            plain_codes.add(entry)

    symptoms = {BINARY_EVIDENCE_TO_SYMPTOM[c] for c in plain_codes if c in BINARY_EVIDENCE_TO_SYMPTOM}
    comorbidities = {BINARY_EVIDENCE_TO_COMORBIDITY[c] for c in plain_codes if c in BINARY_EVIDENCE_TO_COMORBIDITY}

    if has_pain:
        if any(v in chest_locs for v in location_values):
            symptoms.add("chest pain")
        if any(v in abdomen_locs for v in location_values):
            symptoms.add("abdominal pain")
        if any(v in head_locs for v in location_values):
            symptoms.add("headache")

    return sorted(symptoms), sorted(comorbidities)


def select_cases(overlap_conditions: list[str]) -> list[dict[str, Any]]:
    """One test patient per overlapping condition (deterministic, first-match)."""
    chest_locs, abdomen_locs, head_locs = load_location_categories()
    remaining = set(overlap_conditions)
    selected: list[dict[str, Any]] = []

    with open(TEST_PATIENTS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not remaining:
                break
            pathology = row["PATHOLOGY"]
            if pathology not in remaining:
                continue
            evidence_codes = parse_evidence_list(row["EVIDENCES"])
            symptoms, comorbidities = map_evidences(evidence_codes, chest_locs, abdomen_locs, head_locs)
            if not symptoms:
                continue  # skip rows that mapped to nothing usable, try the next matching row
            selected.append(
                {
                    "pathology": pathology,
                    "age": int(float(row["AGE"])),
                    "sex": row["SEX"],
                    "symptoms": symptoms,
                    "comorbidities": comorbidities,
                    "ddxplus_differential": ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"]),
                }
            )
            remaining.discard(pathology)

    return selected


def run_validation() -> dict[str, Any]:
    random.seed(RANDOM_SEED)

    conditions = json.loads(CONDITIONS_JSON.read_text(encoding="utf-8"))
    our_condition_names = {k for k in conditions if k != "_meta"}
    ddx_pathologies: set[str] = set()
    with open(TEST_PATIENTS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ddx_pathologies.add(row["PATHOLOGY"])
    overlap = sorted(our_condition_names & ddx_pathologies)

    cases = select_cases(overlap)
    if len(cases) != len(overlap):
        missing = set(overlap) - {c["pathology"] for c in cases}
        print(f"WARNING: could not find a usable row for: {sorted(missing)}", file=sys.stderr)

    kb = KnowledgeBase()
    supervisor = DiagnosisSupervisor(kb=kb)

    results = []
    exact_matches = 0
    plausible_matches = 0
    wrong = 0

    for case in cases:
        patient_input = {
            "symptoms": case["symptoms"],
            "labs": {},
            "age": case["age"],
            "comorbidities": case["comorbidities"],
        }
        outcome = supervisor.run(patient_input)
        diagnoses = outcome.get("diagnoses", [])
        diagnosis_names = [d["name"] for d in diagnoses]

        top = diagnoses[0] if diagnoses else None
        top_name = top["name"] if top else None
        pathology = case["pathology"]

        if top_name == pathology:
            verdict = "exact_match"
            exact_matches += 1
        elif pathology in diagnosis_names:
            verdict = "plausible"
            plausible_matches += 1
        else:
            verdict = "wrong"
            wrong += 1

        rank = diagnosis_names.index(pathology) + 1 if pathology in diagnosis_names else None

        results.append(
            {
                "pathology": pathology,
                "age": case["age"],
                "sex": case["sex"],
                "input_symptoms": case["symptoms"],
                "input_comorbidities": case["comorbidities"],
                "top_diagnosis": top_name,
                "top_confidence": top["confidence"] if top else None,
                "full_differential": [{"name": d["name"], "confidence": d["confidence"]} for d in diagnoses],
                "pathology_rank_in_our_differential": rank,
                "verdict": verdict,
                "risk_level": (outcome.get("risk_assessment") or {}).get("risk_level"),
                "errors": outcome.get("errors", []),
            }
        )

    summary = {
        "total_cases": len(results),
        "exact_matches": exact_matches,
        "plausible_matches": plausible_matches,
        "wrong": wrong,
        "exact_match_pct": round(exact_matches / len(results) * 100, 1) if results else 0,
        "plausible_or_better_pct": round((exact_matches + plausible_matches) / len(results) * 100, 1)
        if results
        else 0,
    }

    return {"summary": summary, "cases": results}


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TEST_CASES_DIR.mkdir(parents=True, exist_ok=True)

    output = run_validation()

    results_path = RESULTS_DIR / "validation_results.json"
    results_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    cases_path = TEST_CASES_DIR / "selected_cases.json"
    cases_path.write_text(
        json.dumps([{"pathology": c["pathology"], **c} for c in output["cases"]], indent=2), encoding="utf-8"
    )

    print(json.dumps(output["summary"], indent=2))
    print(f"\nFull results: {results_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

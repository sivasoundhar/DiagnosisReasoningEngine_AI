"""Loads and serves the JSON medical knowledge base.

Kept data-driven (JSON in, methods out) per project rules — agents query
this class, they never embed medical facts as Python logic.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("diagnosis_engine.knowledge")

_KB_DIR = Path(__file__).parent

# A value this many multiples beyond the critical threshold isn't a severe clinical
# reading anymore - it's almost certainly a data entry error (wrong units, typo, etc.)
# and should be flagged for verification rather than interpreted clinically.
_IMPLAUSIBLE_MULTIPLIER = 10

# Common abbreviations/synonyms patients or clinicians actually type -> canonical
# symptoms.json key. Kept small and explicit rather than fuzzy-matching, so
# lookups stay predictable and auditable.
SYMPTOM_SYNONYMS: dict[str, str] = {
    "sob": "shortness of breath",
    "dyspnea": "shortness of breath",
    "difficulty breathing": "shortness of breath",
    "rhinorrhea": "runny nose",
    "stuffy nose": "nasal congestion",
    "congestion": "nasal congestion",
    "stomach pain": "abdominal pain",
    "belly pain": "abdominal pain",
    "tiredness": "fatigue",
    "tired": "fatigue",
    "exhaustion": "fatigue",
    "lightheadedness": "dizziness",
    "heart racing": "palpitations",
    "throwing up": "vomiting",
    "acid reflux": "heartburn",
    "myalgia": "muscle aches",
    "body aches": "muscle aches",
    "anorexia": "loss of appetite",
    "leg swelling": "swelling in legs",
    "edema": "swelling in legs",
    "pallor": "pale skin",
    "tachycardia": "rapid heart rate",
    "diaphoresis": "sweating",
    "fainting": "syncope",
    "passed out": "syncope",
    "urticaria": "hives",
    "swollen throat": "throat swelling",
}


class KnowledgeBaseError(Exception):
    """Raised when the KB fails to load or a lookup is fundamentally broken."""


class KnowledgeBase:
    """In-memory lookup over symptoms.json, labs.json, and conditions.json."""

    def __init__(self, kb_dir: Path = _KB_DIR) -> None:
        self.symptoms: dict[str, Any] = self._load_json(kb_dir / "symptoms.json")
        self.labs: dict[str, Any] = self._load_json(kb_dir / "labs.json")
        self.conditions: dict[str, Any] = self._load_json(kb_dir / "conditions.json")
        self.risk_factors: dict[str, Any] = self._load_json(kb_dir / "risk_factors.json")
        self.recommendations: dict[str, Any] = self._load_json(kb_dir / "recommendations.json")

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise KnowledgeBaseError(f"Medical KB file missing: {path}")
        try:
            with path.open(encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseError(f"Invalid JSON in {path}: {exc}") from exc
        data.pop("_meta", None)  # documentation only, not lookup data
        return data

    @staticmethod
    def normalize_symptom(symptom: str) -> str:
        """Lowercase/strip a raw symptom string and resolve it through SYMPTOM_SYNONYMS."""
        key = symptom.strip().lower()
        return SYMPTOM_SYNONYMS.get(key, key)

    def get_diagnoses_for_symptom(self, symptom: str) -> list[dict[str, str]]:
        """Return candidate diagnoses for a single symptom, or [] if unknown."""
        key = self.normalize_symptom(symptom)
        entries = self.symptoms.get(key)
        if entries is None:
            logger.warning("Unknown symptom '%s' - no KB entry, skipping", symptom)
            return []
        return entries

    def interpret_lab(self, lab_name: str, value: float) -> dict[str, Any] | None:
        """Classify a lab value against its reference range. None if lab is unknown."""
        entry = self.labs.get(lab_name)
        if entry is None:
            logger.warning("Unknown lab '%s' - no KB entry, skipping", lab_name)
            return None

        if value <= entry["critical_low"] or value >= entry["critical_high"]:
            status = "CRITICAL"
        elif value < entry["normal_min"]:
            status = "LOW"
        elif value > entry["normal_max"]:
            status = "ELEVATED"
        else:
            status = "NORMAL"

        # A value wildly beyond the critical band (e.g. WBC = 5000) isn't a sicker
        # patient, it's almost certainly a typo or unit mismatch - flag it as such
        # rather than reporting it as a confident clinical finding.
        implausible = value < 0 or value >= entry["critical_high"] * _IMPLAUSIBLE_MULTIPLIER

        interpretation_key = status.lower() if status != "NORMAL" else None
        has_specific_guidance = interpretation_key is not None and interpretation_key in entry["interpretation"]
        interpretation = (
            entry["interpretation"].get(interpretation_key, f"{lab_name} is {status.lower()}")
            if interpretation_key
            else "Within normal limits"
        )

        return {
            "status": status,
            "interpretation": interpretation,
            "unit": entry["unit"],
            "linked_diagnoses": entry.get("linked_diagnoses", []),
            "has_specific_guidance": has_specific_guidance,
            "physiologically_implausible": implausible,
        }

    def get_condition_info(self, condition_name: str) -> dict[str, Any] | None:
        """Return the full definition for a named condition, or None if unknown."""
        info = self.conditions.get(condition_name)
        if info is None:
            logger.warning("Unknown condition '%s' - no KB entry", condition_name)
        return info

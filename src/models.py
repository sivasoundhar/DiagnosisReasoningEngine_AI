"""Pydantic schemas shared across the API and the agent pipeline.

Defined once here so FastAPI request/response validation and the
LangGraph agent state use the exact same shapes — no drift between
"what the API promises" and "what the agents actually produce".
"""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PatientInput(BaseModel):
    """POST /analyze request body."""

    symptoms: list[str] = Field(..., min_length=1, description="e.g. ['fever', 'cough']")
    labs: dict[str, float] = Field(default_factory=dict, description="e.g. {'WBC': 11.2}")
    age: int = Field(..., ge=0, le=120)
    comorbidities: list[str] = Field(default_factory=list, description="e.g. ['diabetes']")
    patient_id: str | None = Field(default=None, description="Optional, for history tracking - server generates a UUID4 if omitted")
    patient_name: str | None = Field(default=None, max_length=256, description="Optional display name, for history/reports")


class DiagnosisCandidate(BaseModel):
    """One differential diagnosis produced by the Symptom Analyzer."""

    name: str
    confidence: float = Field(..., ge=0, le=100)
    reasoning: str


class LabInterpretation(BaseModel):
    """One lab value interpreted by the Lab Interpreter."""

    lab_name: str
    value: float
    status: str = Field(..., description="LOW | NORMAL | ELEVATED | CRITICAL")
    interpretation: str
    confidence: float = Field(..., ge=0, le=100)


class RiskAssessment(BaseModel):
    """Output of the Risk Assessor."""

    risk_level: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    score: int = Field(..., ge=0)
    reasoning: str
    likely_complications: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Output of the Recommender."""

    tests: list[str] = Field(default_factory=list)
    treatments: list[str] = Field(default_factory=list)
    follow_up: str


class AIOpinionDiagnosis(BaseModel):
    """One candidate diagnosis from the AI Reasoning Agent's independent LLM call."""

    name: str
    confidence: float = Field(..., ge=0, le=100)
    reasoning: str


class AIOpinion(BaseModel):
    """Output of the AI Reasoning Agent — a genuine, independent LLM second opinion.

    Deliberately separate from `diagnoses` (the rule engine's output): this is a
    supplementary, clearly-labeled opinion for a clinician to compare against the
    auditable rule-based result, not a replacement for it. `None` on the parent
    `DiagnosisOutput` when no GROQ_API_KEY is configured or the LLM call failed —
    the rest of the response is unaffected either way.
    """

    diagnoses: list[AIOpinionDiagnosis] = Field(default_factory=list)
    summary: str = ""
    red_flags: list[str] = Field(default_factory=list)
    model: str = Field(default="", description="Which Groq model produced this opinion")


class AICritique(BaseModel):
    """Output of the AI Critic Agent — an LLM cross-check of the rule-based result.

    Unlike `AIOpinion` (an independent take that never sees the rule engine's output), this
    agent *is* shown `diagnoses`/`risk_assessment`/`recommendation` and asked to critique that
    specific result. This is the actual cross-verification step. `None` on `DiagnosisOutput`
    when no GROQ_API_KEY is configured or the LLM call failed — same as `ai_opinion`, never
    required for the rest of the response to be usable.
    """

    assessment: str = Field(..., description="agrees | partially_agrees | disagrees")
    concerns: list[str] = Field(default_factory=list, description="Specific issues with the rule-based result")
    missed_considerations: list[str] = Field(
        default_factory=list, description="Clinically relevant things the rule-based result didn't consider"
    )
    narrative: str = ""
    model: str = Field(default="", description="Which Groq model produced this critique")


class DiagnosisOutput(BaseModel):
    """POST /analyze response body — the full reasoning chain, not just an answer."""

    patient_id: str = Field(..., description="Echoed if provided, otherwise server-generated (UUID4)")
    patient_name: str | None = Field(default=None, description="Echoed if provided on the request")
    diagnoses: list[DiagnosisCandidate]
    lab_interpretations: list[LabInterpretation] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    recommendation: Recommendation | None = None
    ai_opinion: AIOpinion | None = Field(
        default=None, description="Independent LLM second opinion, absent if no GROQ_API_KEY is configured"
    )
    ai_critique: AICritique | None = Field(
        default=None,
        description="LLM cross-check of the rule-based result above, absent if no GROQ_API_KEY is configured",
    )
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HistoryEntry(BaseModel):
    """One row returned by GET /history/{patient_id}."""

    id: int
    patient_id: str
    patient_name: str | None = None
    created_at: datetime
    symptoms: list[str]
    age: int | None = None
    comorbidities: list[str] = Field(default_factory=list)
    result: DiagnosisOutput


class FeedbackInput(BaseModel):
    """POST /feedback request body."""

    patient_id: str
    actual_diagnosis: str
    feedback_text: str | None = None


class ErrorResponse(BaseModel):
    """Uniform JSON error shape for all error handlers."""

    error: str
    detail: str | None = None


class DiagnosisFrequency(BaseModel):
    """How often a diagnosis has come out on top of the differential."""

    name: str
    count: int = Field(..., ge=0)


class AnalyticsSummary(BaseModel):
    """GET /analytics response body — aggregated over every stored PatientRecord.

    Computed on demand from result_json (no separate stats table), since the
    dataset a demo instance accumulates is small enough that a full scan per
    request is simpler than keeping running counters in sync.
    """

    total_analyses: int = Field(..., ge=0, description="Row count in patient_records")
    unique_patients: int = Field(..., ge=0, description="Distinct patient_id count")
    risk_level_distribution: dict[str, int] = Field(
        default_factory=dict, description="e.g. {'LOW': 3, 'MEDIUM': 5, 'HIGH': 2, 'CRITICAL': 1}"
    )
    top_diagnoses: list[DiagnosisFrequency] = Field(
        default_factory=list, description="Most frequent #1 (highest-confidence) diagnosis, desc by count"
    )
    records_with_feedback: int = Field(..., ge=0)
    feedback_coverage_pct: float = Field(..., ge=0, le=100, description="records_with_feedback / total_analyses * 100")
    first_analysis_at: datetime | None = None
    last_analysis_at: datetime | None = None

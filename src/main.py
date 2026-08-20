"""FastAPI entrypoint.

Day 1: app wiring, CORS, logging, health check.
Day 7: /analyze, /history/{patient_id}, /feedback wired to the Day 6 supervisor + DB.
"""
import json
import logging
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.agents.base_agent import AgentError
from src.config import get_settings
from src.database import PatientRecord, get_db, init_db
from src.models import (
    AICritique,
    AIOpinion,
    AIOpinionDiagnosis,
    AnalyticsSummary,
    DiagnosisCandidate,
    DiagnosisFrequency,
    DiagnosisOutput,
    ErrorResponse,
    FeedbackInput,
    HistoryEntry,
    LabInterpretation,
    PatientInput,
    Recommendation,
    RiskAssessment,
)
from src.orchestrator.supervisor import DiagnosisSupervisor

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("diagnosis_engine")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Diagnosis Reasoning Engine starting up (environment=%s)", settings.environment)
    init_db()
    # Built once at startup, not per-request: loads the KB JSON and compiles all 5
    # LangGraph graphs (4 agents + supervisor) a single time for the app's lifetime.
    app.state.supervisor = DiagnosisSupervisor()
    yield
    logger.info("Diagnosis Reasoning Engine shutting down")


app = FastAPI(
    title="Diagnosis Reasoning Engine",
    description="Multi-agent clinical decision support system.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Liveness probe for local dev, Docker, and Render."""
    return {"status": "healthy"}


def get_supervisor(request: Request) -> DiagnosisSupervisor:
    """Fetch the single supervisor instance built at startup (see lifespan)."""
    return request.app.state.supervisor


def _generate_patient_id() -> str:
    """MRN-style id (e.g. PT-20260812-A1B2C3) for when the caller doesn't supply
    their own patient_id - reads like a real hospital record number instead of
    a raw UUID4, while still being effectively collision-free (uuid4-derived
    suffix)."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"PT-{date_part}-{suffix}"


def _build_diagnosis_output(patient_id: str, patient_name: str | None, result: dict) -> DiagnosisOutput:
    """Map the supervisor's raw dict result onto the DiagnosisOutput schema.

    Built with explicit field-by-field construction (not **result unpacking) so a
    future field added to an agent's output dict can't silently leak into the API
    response schema without a deliberate decision to expose it.
    """
    risk = result.get("risk_assessment")
    rec = result.get("recommendation")
    ai_opinion = result.get("ai_opinion")
    ai_critique = result.get("ai_critique")
    return DiagnosisOutput(
        patient_id=patient_id,
        patient_name=patient_name,
        diagnoses=[
            DiagnosisCandidate(name=d["name"], confidence=d["confidence"], reasoning=d["reasoning"])
            for d in result.get("diagnoses", [])
        ],
        lab_interpretations=[
            LabInterpretation(
                lab_name=li["lab_name"],
                value=li["value"],
                status=li["status"],
                interpretation=li["interpretation"],
                confidence=li["confidence"],
            )
            for li in result.get("lab_interpretations", [])
        ],
        risk_assessment=(
            RiskAssessment(
                risk_level=risk["risk_level"],
                score=risk["score"],
                reasoning=risk["reasoning"],
                likely_complications=risk.get("likely_complications", []),
            )
            if risk
            else None
        ),
        recommendation=(
            Recommendation(
                tests=rec.get("tests", []),
                treatments=rec.get("treatments", []),
                follow_up=rec.get("follow_up", ""),
            )
            if rec
            else None
        ),
        ai_opinion=(
            AIOpinion(
                diagnoses=[
                    AIOpinionDiagnosis(name=d["name"], confidence=d["confidence"], reasoning=d["reasoning"])
                    for d in ai_opinion.get("diagnoses", [])
                ],
                summary=ai_opinion.get("summary", ""),
                red_flags=ai_opinion.get("red_flags", []),
                model=ai_opinion.get("model", ""),
            )
            if ai_opinion
            else None
        ),
        ai_critique=(
            AICritique(
                assessment=ai_critique.get("assessment", "partially_agrees"),
                concerns=ai_critique.get("concerns", []),
                missed_considerations=ai_critique.get("missed_considerations", []),
                narrative=ai_critique.get("narrative", ""),
                model=ai_critique.get("model", ""),
            )
            if ai_critique
            else None
        ),
    )


@app.post("/analyze", response_model=DiagnosisOutput, tags=["diagnosis"])
def analyze_patient(
    patient: PatientInput,
    db: Session = Depends(get_db),
    supervisor: DiagnosisSupervisor = Depends(get_supervisor),
) -> DiagnosisOutput:
    """Run the full 4-agent pipeline on a patient and persist the result for /history."""
    try:
        result = supervisor.run(patient.model_dump())
    except AgentError as exc:
        # Covers both SupervisorError (symptom analysis itself failed) and any other
        # agent raising unexpectedly - both are "the pipeline crashed", i.e. a 500.
        logger.error("Diagnosis pipeline failed: %s", exc, exc_info=exc)
        raise HTTPException(status_code=500, detail="Diagnosis pipeline failed. Please try again.") from exc

    patient_id = patient.patient_id or _generate_patient_id()
    output = _build_diagnosis_output(patient_id, patient.patient_name, result)

    record = PatientRecord(
        patient_id=patient_id,
        patient_name=patient.patient_name,
        symptoms_json=json.dumps(patient.symptoms),
        labs_json=json.dumps(patient.labs),
        age=patient.age,
        comorbidities_json=json.dumps(patient.comorbidities),
        result_json=output.model_dump_json(),
    )
    db.add(record)
    db.commit()

    return output


@app.get("/history/{patient_id}", response_model=list[HistoryEntry], tags=["diagnosis"])
def get_patient_history(patient_id: str, db: Session = Depends(get_db)) -> list[HistoryEntry]:
    """Past analyses for a patient, most recent first."""
    records = (
        db.query(PatientRecord)
        .filter(PatientRecord.patient_id == patient_id)
        .order_by(PatientRecord.created_at.desc())
        .all()
    )
    if not records:
        raise HTTPException(status_code=404, detail=f"No history found for patient_id '{patient_id}'.")

    return [
        HistoryEntry(
            id=r.id,
            patient_id=r.patient_id,
            patient_name=r.patient_name,
            created_at=r.created_at,
            symptoms=json.loads(r.symptoms_json),
            age=r.age,
            comorbidities=json.loads(r.comorbidities_json) if r.comorbidities_json else [],
            result=DiagnosisOutput.model_validate_json(r.result_json),
        )
        for r in records
    ]


@app.post("/feedback", tags=["diagnosis"])
def submit_feedback(feedback: FeedbackInput, db: Session = Depends(get_db)) -> dict[str, str]:
    """Attach a clinician's actual diagnosis / free-text feedback to a patient's latest analysis."""
    record = (
        db.query(PatientRecord)
        .filter(PatientRecord.patient_id == feedback.patient_id)
        .order_by(PatientRecord.created_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"No record found for patient_id '{feedback.patient_id}'.")

    record.actual_diagnosis = feedback.actual_diagnosis
    record.feedback_text = feedback.feedback_text
    db.commit()

    return {"status": "success", "message": "Feedback recorded."}


@app.get("/analytics", response_model=AnalyticsSummary, tags=["diagnosis"])
def get_analytics(db: Session = Depends(get_db)) -> AnalyticsSummary:
    """Aggregate stats across every stored analysis (all patients, not one).

    Full-table scan + in-Python aggregation rather than SQL aggregates,
    since the fields that matter (risk_level, top diagnosis name) live
    inside result_json, not their own columns - fine at demo-app scale.
    """
    records = db.query(PatientRecord).order_by(PatientRecord.created_at.asc()).all()

    if not records:
        return AnalyticsSummary(
            total_analyses=0,
            unique_patients=0,
            risk_level_distribution={},
            top_diagnoses=[],
            records_with_feedback=0,
            feedback_coverage_pct=0.0,
            first_analysis_at=None,
            last_analysis_at=None,
        )

    risk_counts: Counter[str] = Counter()
    top_diagnosis_counts: Counter[str] = Counter()
    unique_patient_ids: set[str] = set()
    records_with_feedback = 0

    for r in records:
        unique_patient_ids.add(r.patient_id)
        if r.actual_diagnosis:
            records_with_feedback += 1
        try:
            result = DiagnosisOutput.model_validate_json(r.result_json)
        except ValueError:
            logger.warning("Skipping unparseable result_json for record id=%s in /analytics", r.id)
            continue
        if result.risk_assessment is not None:
            risk_counts[result.risk_assessment.risk_level] += 1
        if result.diagnoses:
            top_diagnosis_counts[result.diagnoses[0].name] += 1

    total = len(records)
    top_diagnoses = [
        DiagnosisFrequency(name=name, count=count)
        for name, count in sorted(top_diagnosis_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    return AnalyticsSummary(
        total_analyses=total,
        unique_patients=len(unique_patient_ids),
        risk_level_distribution=dict(risk_counts),
        top_diagnoses=top_diagnoses,
        records_with_feedback=records_with_feedback,
        feedback_coverage_pct=round(records_with_feedback / total * 100, 1) if total else 0.0,
        first_analysis_at=records[0].created_at,
        last_analysis_at=records[-1].created_at,
    )


# --- Error handlers: always return JSON, never let a stack trace leak to clients ---


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic input validation failures (e.g. missing symptoms) -> 400, not FastAPI's default 422."""
    logger.warning("400 Bad Request (validation) on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error="bad_request", detail=str(exc.errors())).model_dump(),
    )


@app.exception_handler(400)
async def bad_request_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("400 Bad Request on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error="bad_request", detail=str(exc)).model_dump(),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.info("404 Not Found on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(error="not_found", detail=str(exc)).model_dump(),
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the real exception server-side; never echo internals to the client.
    logger.error("500 Internal Server Error on %s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(error="internal_server_error", detail="Something went wrong.").model_dump(),
    )

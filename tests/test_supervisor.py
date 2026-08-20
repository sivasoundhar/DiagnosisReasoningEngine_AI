"""Tests for the Day 6 LangGraph Supervisor (full agent pipeline)."""
import pytest

from src.agents.base_agent import AgentError
from src.knowledge.medical_kb import KnowledgeBase
from src.orchestrator.supervisor import DiagnosisSupervisor, SupervisorError


class _FakeAIReasoner:
    """Stands in for AIReasonerAgent in tests that aren't specifically about the Day 12
    AI feature - succeeds deterministically so pre-existing pipeline assertions (e.g.
    `errors == []`) stay meaningful without any test here touching the network."""

    name = "ai_reasoner"

    def run(self, input_data: dict) -> dict:
        return {
            "diagnoses": [{"name": "Pneumonia", "confidence": 70, "reasoning": "stub AI reasoning"}],
            "summary": "stub AI opinion",
            "red_flags": [],
            "model": "fake-model",
        }


class _FailingAIReasoner:
    """Simulates the real degrade-gracefully case: no GROQ_API_KEY / a failed Groq call."""

    name = "ai_reasoner"

    def run(self, input_data: dict) -> dict:
        raise AgentError("No LLM configured (GROQ_API_KEY unset) - AI reasoning agent is unavailable.")


class _FakeAICritic:
    """Stands in for AICriticAgent in tests that aren't specifically about the Day 13
    cross-verification feature."""

    name = "ai_critic"

    def run(self, input_data: dict) -> dict:
        return {
            "assessment": "agrees",
            "concerns": [],
            "missed_considerations": [],
            "narrative": "stub AI critique",
            "model": "fake-model",
        }


class _FailingAICritic:
    """Simulates the real degrade-gracefully case: no GROQ_API_KEY / a failed Groq call."""

    name = "ai_critic"

    def run(self, input_data: dict) -> dict:
        raise AgentError("No LLM configured (GROQ_API_KEY unset) - AI Critic agent is unavailable.")


@pytest.fixture
def supervisor(knowledge_base: KnowledgeBase) -> DiagnosisSupervisor:
    return DiagnosisSupervisor(kb=knowledge_base, ai_reasoner=_FakeAIReasoner(), ai_critic=_FakeAICritic())


def test_constructs_without_error(supervisor: DiagnosisSupervisor) -> None:
    assert supervisor.symptom_analyzer.name == "symptom_analyzer"
    assert supervisor.lab_interpreter.name == "lab_interpreter"
    assert supervisor.risk_assessor.name == "risk_assessor"
    assert supervisor.recommender.name == "recommender"
    assert supervisor.ai_reasoner.name == "ai_reasoner"
    assert supervisor.ai_critic.name == "ai_critic"


def test_full_pipeline_end_to_end(supervisor: DiagnosisSupervisor, sample_patient: dict) -> None:
    result = supervisor.run(sample_patient)

    assert len(result["diagnoses"]) > 0
    assert result["diagnoses"][0]["name"] == "Pneumonia"  # fever+cough+SOB triad, per Day 2's own example

    assert len(result["lab_interpretations"]) == 2  # WBC + CRP

    assert result["risk_assessment"] is not None
    assert result["risk_assessment"]["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    assert result["recommendation"] is not None
    assert len(result["recommendation"]["tests"]) > 0
    assert len(result["recommendation"]["treatments"]) > 0

    assert result["errors"] == []


def test_agent_order_risk_uses_top_diagnosis(supervisor: DiagnosisSupervisor) -> None:
    # Symptom Analyzer's top diagnosis must flow into Risk Assessor's primary_diagnosis.
    result = supervisor.run({"symptoms": ["fever", "cough", "SOB"], "age": 45})
    assert result["diagnoses"][0]["name"] == "Pneumonia"
    assert "Pneumonia" in result["risk_assessment"]["reasoning"]


def test_state_flows_risk_level_into_recommendation(supervisor: DiagnosisSupervisor) -> None:
    # Risk Assessor's output risk_level must flow into the Recommender's risk_level input,
    # driving setting/follow_up (elderly + comorbidities + severe symptom -> high risk -> inpatient-ish).
    result = supervisor.run(
        {
            "symptoms": ["fever", "cough", "SOB"],
            "age": 80,
            "comorbidities": ["diabetes", "heart disease", "kidney disease"],
        }
    )
    risk_level = result["risk_assessment"]["risk_level"]
    assert risk_level in {"HIGH", "CRITICAL"}
    assert result["recommendation"]["risk_level_used"] == risk_level
    assert result["recommendation"]["setting"] in {"inpatient", "ICU"}


def test_elderly_age_flows_into_recommendation_extra_tests(supervisor: DiagnosisSupervisor) -> None:
    result = supervisor.run({"symptoms": ["fever", "cough"], "age": 80})
    assert "ECG (baseline cardiac assessment)" in result["recommendation"]["tests"]


def test_missing_labs_degrades_gracefully(supervisor: DiagnosisSupervisor) -> None:
    result = supervisor.run({"symptoms": ["fever", "cough"], "age": 40})
    assert result["lab_interpretations"] == []
    assert result["errors"] == []


def test_unknown_symptoms_surfaced_not_crashed(supervisor: DiagnosisSupervisor) -> None:
    result = supervisor.run({"symptoms": ["fever", "xyz123"], "age": 40})
    assert "xyz123" in result["unknown_symptoms"]
    # Pipeline still completes fully despite one unrecognized symptom.
    assert result["recommendation"] is not None


def test_all_unknown_symptoms_still_completes_with_generic_workup(supervisor: DiagnosisSupervisor) -> None:
    result = supervisor.run({"symptoms": ["totally_unknown_symptom"], "age": 40})
    assert result["diagnoses"] == []
    assert result["risk_assessment"] is not None
    assert result["recommendation"] is not None
    assert len(result["recommendation"]["tests"]) > 0  # generic fallback workup, never empty


def test_empty_symptoms_raises_supervisor_error(supervisor: DiagnosisSupervisor) -> None:
    with pytest.raises(SupervisorError):
        supervisor.run({"symptoms": [], "age": 40})


def test_supervisor_error_is_an_agent_error(supervisor: DiagnosisSupervisor) -> None:
    # So callers (Day 7's API layer) can catch AgentError generically for all agent/pipeline failures.
    assert issubclass(SupervisorError, AgentError)


def test_flagged_lab_value_surfaced_not_silently_dropped(supervisor: DiagnosisSupervisor) -> None:
    result = supervisor.run({"symptoms": ["fever"], "labs": {"WBC": 500000}, "age": 40})
    flagged = [i for i in result["lab_interpretations"] if i["flagged"]]
    assert len(flagged) == 1
    assert "WBC" in result["flagged_labs"]


def test_reasoning_present_throughout_the_chain(supervisor: DiagnosisSupervisor, sample_patient: dict) -> None:
    result = supervisor.run(sample_patient)
    assert result["diagnoses"][0]["reasoning"]
    assert result["risk_assessment"]["reasoning"]
    assert result["recommendation"]["reasoning_summary"]


def test_ai_opinion_included_when_reasoner_succeeds(
    supervisor: DiagnosisSupervisor, sample_patient: dict
) -> None:
    result = supervisor.run(sample_patient)
    assert result["ai_opinion"] is not None
    assert result["ai_opinion"]["diagnoses"][0]["name"] == "Pneumonia"
    assert result["errors"] == []


def test_ai_opinion_receives_only_original_input_not_rule_engine_output(
    knowledge_base: KnowledgeBase, sample_patient: dict
) -> None:
    """The AI Reasoner must never see diagnoses/risk_assessment/recommendation - only the
    same raw fields the Symptom Analyzer started from. Asserted by inspecting exactly what
    gets passed into `run()`."""
    captured: dict = {}

    class _CapturingAIReasoner:
        name = "ai_reasoner"

        def run(self, input_data: dict) -> dict:
            captured.update(input_data)
            return {"diagnoses": [], "summary": "stub", "red_flags": [], "model": "fake"}

    supervisor = DiagnosisSupervisor(kb=knowledge_base, ai_reasoner=_CapturingAIReasoner())
    supervisor.run(sample_patient)

    assert set(captured.keys()) == {"symptoms", "labs", "age", "comorbidities"}
    assert captured["symptoms"] == sample_patient["symptoms"]


def test_ai_reasoner_failure_degrades_gracefully_pipeline_still_completes(
    knowledge_base: KnowledgeBase, sample_patient: dict
) -> None:
    supervisor = DiagnosisSupervisor(kb=knowledge_base, ai_reasoner=_FailingAIReasoner(), ai_critic=_FakeAICritic())
    result = supervisor.run(sample_patient)

    assert result["ai_opinion"] is None
    assert any(e["stage"] == "ai_reasoner" for e in result["errors"])
    # The rest of the pipeline is entirely unaffected by the AI opinion failing.
    assert result["diagnoses"][0]["name"] == "Pneumonia"
    assert result["risk_assessment"] is not None
    assert result["recommendation"] is not None


def test_ai_critique_included_when_critic_succeeds(
    supervisor: DiagnosisSupervisor, sample_patient: dict
) -> None:
    result = supervisor.run(sample_patient)
    assert result["ai_critique"] is not None
    assert result["ai_critique"]["assessment"] == "agrees"
    assert result["errors"] == []


def test_ai_critique_receives_rule_based_result_unlike_ai_opinion(
    knowledge_base: KnowledgeBase, sample_patient: dict
) -> None:
    """The whole point of AI Critic (vs AI Reasoner) is that it DOES see the rule engine's
    output - assert that explicitly, the opposite of what's asserted for AI Reasoner above."""
    captured: dict = {}

    class _CapturingAICritic:
        name = "ai_critic"

        def run(self, input_data: dict) -> dict:
            captured.update(input_data)
            return {"assessment": "agrees", "concerns": [], "missed_considerations": [], "narrative": "stub", "model": "fake"}

    supervisor = DiagnosisSupervisor(kb=knowledge_base, ai_reasoner=_FakeAIReasoner(), ai_critic=_CapturingAICritic())
    supervisor.run(sample_patient)

    assert set(captured.keys()) == {
        "symptoms", "labs", "age", "comorbidities", "diagnoses", "risk_assessment", "recommendation",
    }
    assert captured["diagnoses"][0]["name"] == "Pneumonia"
    assert captured["risk_assessment"] is not None
    assert captured["recommendation"] is not None


def test_ai_critic_failure_degrades_gracefully_pipeline_still_completes(
    knowledge_base: KnowledgeBase, sample_patient: dict
) -> None:
    supervisor = DiagnosisSupervisor(kb=knowledge_base, ai_reasoner=_FakeAIReasoner(), ai_critic=_FailingAICritic())
    result = supervisor.run(sample_patient)

    assert result["ai_critique"] is None
    assert any(e["stage"] == "ai_critic" for e in result["errors"])
    # The rest of the pipeline, including the independent AI opinion, is unaffected.
    assert result["diagnoses"][0]["name"] == "Pneumonia"
    assert result["ai_opinion"] is not None

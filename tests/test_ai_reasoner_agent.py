"""Tests for the AI Reasoning Agent (independent LLM second opinion).

No test here ever hits the network - a fake LLM object is injected in place of
`ChatGroq`, so these test the agent's own logic (case summary building, output
shaping, error handling), not Groq's API.
"""
import pytest

from src.agents.ai_reasoner import AIOpinionDiagnosis, AIOpinionSchema, AIReasonerAgent
from src.agents.base_agent import AgentError


class _FakeStructuredLLM:
    """Stands in for `llm.with_structured_output(schema)` - either returns a fixed
    response or raises a fixed exception, whichever the test wired up."""

    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def invoke(self, messages):
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeChatGroq:
    """Stands in for `ChatGroq` - `with_structured_output` returns a `_FakeStructuredLLM`."""

    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def with_structured_output(self, schema):
        return _FakeStructuredLLM(response=self._response, exc=self._exc)


@pytest.fixture
def sample_opinion() -> AIOpinionSchema:
    return AIOpinionSchema(
        diagnoses=[
            AIOpinionDiagnosis(name="Pneumonia", confidence=80, reasoning="fever+cough+SOB cluster fits bacterial pneumonia"),
            AIOpinionDiagnosis(name="Influenza", confidence=30, reasoning="fever+cough also fit, less specific"),
        ],
        summary="Likely bacterial pneumonia given the symptom cluster; consider chest imaging.",
        red_flags=["shortness of breath"],
    )


def test_returns_diagnoses_summary_and_red_flags(sample_opinion: AIOpinionSchema) -> None:
    agent = AIReasonerAgent(llm=_FakeChatGroq(response=sample_opinion), model_name="llama-3.3-70b-versatile")
    result = agent.run({"symptoms": ["fever", "cough", "shortness of breath"], "age": 62})

    assert result["diagnoses"][0]["name"] == "Pneumonia"
    assert result["diagnoses"][0]["confidence"] == 80
    assert "pneumonia" in result["summary"].lower()
    assert "shortness of breath" in result["red_flags"]
    assert result["model"] == "llama-3.3-70b-versatile"


def test_caps_at_five_diagnoses() -> None:
    many = AIOpinionSchema(
        diagnoses=[AIOpinionDiagnosis(name=f"Condition {i}", confidence=50, reasoning="stub") for i in range(8)],
        summary="stub",
    )
    agent = AIReasonerAgent(llm=_FakeChatGroq(response=many))
    result = agent.run({"symptoms": ["fever"], "age": 40})
    assert len(result["diagnoses"]) == 5


def test_no_llm_configured_raises_agent_error() -> None:
    agent = AIReasonerAgent(llm=None)
    with pytest.raises(AgentError):
        agent.run({"symptoms": ["fever"], "age": 40})


def test_llm_call_failure_raises_agent_error() -> None:
    agent = AIReasonerAgent(llm=_FakeChatGroq(exc=RuntimeError("Groq timeout")))
    with pytest.raises(AgentError):
        agent.run({"symptoms": ["fever"], "age": 40})


def test_case_summary_includes_labs_and_comorbidities(sample_opinion: AIOpinionSchema) -> None:
    """Indirect check: the agent runs end-to-end on the full input shape without error,
    including labs/comorbidities fields the other agents also consume."""
    agent = AIReasonerAgent(llm=_FakeChatGroq(response=sample_opinion))
    result = agent.run(
        {
            "symptoms": ["fever"],
            "labs": {"WBC": 12.5},
            "age": 60,
            "comorbidities": ["diabetes"],
        }
    )
    assert result["diagnoses"]


def test_missing_optional_fields_default_safely(sample_opinion: AIOpinionSchema) -> None:
    """No labs/age/comorbidities provided - shouldn't crash building the case summary."""
    agent = AIReasonerAgent(llm=_FakeChatGroq(response=sample_opinion))
    result = agent.run({"symptoms": ["fever"]})
    assert result["diagnoses"]


def test_get_reasoning_falls_back_when_no_summary() -> None:
    agent = AIReasonerAgent(llm=None)
    assert agent.get_reasoning({}) == "No AI reasoning produced."

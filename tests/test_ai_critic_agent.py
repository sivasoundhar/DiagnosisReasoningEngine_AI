"""Tests for the AI Critic Agent (Day 13: LLM cross-check of the rule-based result).

No test here ever hits the network - a fake LLM object is injected in place of
`ChatGroq`, same pattern as tests/test_ai_reasoner_agent.py.
"""
import pytest

from src.agents.ai_critic import AICriticAgent, AICritiqueSchema
from src.agents.base_agent import AgentError


class _FakeStructuredLLM:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def invoke(self, messages):
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeChatGroq:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def with_structured_output(self, schema):
        return _FakeStructuredLLM(response=self._response, exc=self._exc)


@pytest.fixture
def rule_based_result() -> dict:
    return {
        "symptoms": ["fever", "cough", "shortness of breath"],
        "labs": {"WBC": 12.5},
        "age": 62,
        "comorbidities": ["diabetes"],
        "diagnoses": [{"name": "Pneumonia", "confidence": 100.0, "reasoning": "stub"}],
        "risk_assessment": {"risk_level": "CRITICAL", "score": 80, "reasoning": "stub"},
        "recommendation": {"tests": ["Chest X-ray"], "treatments": ["Antibiotics"], "follow_up": "48h"},
    }


def test_agrees_assessment_passes_through(rule_based_result: dict) -> None:
    response = AICritiqueSchema(assessment="agrees", concerns=[], missed_considerations=[], narrative="Sound result.")
    agent = AICriticAgent(llm=_FakeChatGroq(response=response), model_name="llama-3.3-70b-versatile")
    result = agent.run(rule_based_result)

    assert result["assessment"] == "agrees"
    assert result["concerns"] == []
    assert result["narrative"] == "Sound result."
    assert result["model"] == "llama-3.3-70b-versatile"


def test_disagrees_with_concerns_and_missed_considerations(rule_based_result: dict) -> None:
    response = AICritiqueSchema(
        assessment="disagrees",
        concerns=["Confidence seems overstated given only 3 symptoms"],
        missed_considerations=["Should rule out pulmonary embolism given SOB"],
        narrative="The differential is too narrow.",
    )
    agent = AICriticAgent(llm=_FakeChatGroq(response=response))
    result = agent.run(rule_based_result)

    assert result["assessment"] == "disagrees"
    assert "pulmonary embolism" in result["missed_considerations"][0].lower()
    assert len(result["concerns"]) == 1


def test_unrecognized_assessment_defaults_to_partially_agrees(rule_based_result: dict) -> None:
    response = AICritiqueSchema(assessment="mostly fine I guess", narrative="stub")
    agent = AICriticAgent(llm=_FakeChatGroq(response=response))
    result = agent.run(rule_based_result)
    assert result["assessment"] == "partially_agrees"


def test_assessment_case_and_whitespace_normalized(rule_based_result: dict) -> None:
    response = AICritiqueSchema(assessment="  AGREES  ", narrative="stub")
    agent = AICriticAgent(llm=_FakeChatGroq(response=response))
    result = agent.run(rule_based_result)
    assert result["assessment"] == "agrees"


def test_no_llm_configured_raises_agent_error(rule_based_result: dict) -> None:
    agent = AICriticAgent(llm=None)
    with pytest.raises(AgentError):
        agent.run(rule_based_result)


def test_llm_call_failure_raises_agent_error(rule_based_result: dict) -> None:
    agent = AICriticAgent(llm=_FakeChatGroq(exc=RuntimeError("Groq timeout")))
    with pytest.raises(AgentError):
        agent.run(rule_based_result)


def test_review_context_includes_rule_based_result_not_just_case(rule_based_result: dict) -> None:
    """The whole point of this agent is seeing the rule engine's output - confirm the review
    context actually contains it, not just the raw case (that would make it AI Reasoner again)."""
    captured = {}

    class _CapturingLLM:
        def with_structured_output(self, schema):
            class _Inner:
                def invoke(self, messages):
                    captured["context"] = messages[-1].content
                    return AICritiqueSchema(assessment="agrees", narrative="stub")

            return _Inner()

    agent = AICriticAgent(llm=_CapturingLLM())
    agent.run(rule_based_result)

    assert "Pneumonia" in captured["context"]
    assert "CRITICAL" in captured["context"]
    assert "Chest X-ray" in captured["context"]


def test_missing_rule_based_result_does_not_crash(rule_based_result: dict) -> None:
    """diagnoses/risk_assessment/recommendation all missing/None - still builds a valid review
    context and runs (e.g. supervisor calling this before those stages ever ran)."""
    response = AICritiqueSchema(assessment="agrees", narrative="stub")
    agent = AICriticAgent(llm=_FakeChatGroq(response=response))
    result = agent.run({"symptoms": ["fever"], "age": 40})
    assert result["assessment"] == "agrees"


def test_get_reasoning_falls_back_when_no_narrative() -> None:
    agent = AICriticAgent(llm=None)
    assert agent.get_reasoning({}) == "No AI critique produced."

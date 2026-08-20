"""Tests for the Risk Assessor agent.

Spec test cases used diagnosis names like "mild cold" as shorthand; since our
diagnosis-severity lookup is exact-name against conditions.json (data-driven,
not free-text parsing), the equivalent real KB entries are used instead
(e.g. URTI for "mild cold", Sepsis for "sepsis").
"""
import pytest

from src.agents.base_agent import AgentError
from src.agents.risk_assessor import RiskAssessorAgent
from src.knowledge.medical_kb import KnowledgeBase


@pytest.fixture
def agent(knowledge_base: KnowledgeBase) -> RiskAssessorAgent:
    return RiskAssessorAgent(kb=knowledge_base)


def test_imports_and_constructs_without_error(agent: RiskAssessorAgent) -> None:
    assert agent.name == "risk_assessor"


def test_middle_aged_pneumonia_no_comorbidities_is_medium(agent: RiskAssessorAgent) -> None:
    result = agent.run({"age": 45, "comorbidities": [], "primary_diagnosis": "Pneumonia"})
    assert result["risk_level"] == "MEDIUM"


def test_elderly_multi_comorbid_pneumonia_with_sob_is_high_or_critical(agent: RiskAssessorAgent) -> None:
    result = agent.run(
        {
            "age": 75,
            "comorbidities": ["diabetes", "heart disease"],
            "primary_diagnosis": "Pneumonia",
            "severity_indicators": ["SOB"],
        }
    )
    assert result["risk_level"] in {"HIGH", "CRITICAL"}


def test_young_healthy_mild_illness_is_low(agent: RiskAssessorAgent) -> None:
    result = agent.run({"age": 25, "comorbidities": [], "primary_diagnosis": "URTI"})
    assert result["risk_level"] == "LOW"


def test_elderly_multi_comorbid_sepsis_with_sob_is_critical(agent: RiskAssessorAgent) -> None:
    result = agent.run(
        {
            "age": 80,
            "comorbidities": ["diabetes", "heart disease", "kidney disease"],
            "primary_diagnosis": "Sepsis",
            "severity_indicators": ["SOB"],
        }
    )
    assert result["risk_level"] == "CRITICAL"


def test_missing_data_handled_gracefully(agent: RiskAssessorAgent) -> None:
    result = agent.run({})
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert result["score"] >= 0


def test_age_increases_risk_monotonically(agent: RiskAssessorAgent) -> None:
    young = agent.run({"age": 25})
    old = agent.run({"age": 80})
    assert old["score"] > young["score"]


def test_comorbidities_increase_risk(agent: RiskAssessorAgent) -> None:
    without = agent.run({"age": 45})
    with_comorbidity = agent.run({"age": 45, "comorbidities": ["cancer"]})
    assert with_comorbidity["score"] > without["score"]


def test_invalid_age_falls_back_to_default_without_crashing(agent: RiskAssessorAgent) -> None:
    result = agent.run({"age": 500})
    assert result["score"] >= 0


def test_unknown_comorbidity_skipped_gracefully(agent: RiskAssessorAgent) -> None:
    baseline = agent.run({"age": 40})
    with_unknown = agent.run({"age": 40, "comorbidities": ["not_a_real_comorbidity"]})
    assert with_unknown["score"] == baseline["score"]


def test_unknown_diagnosis_uses_generic_score_without_crashing(agent: RiskAssessorAgent) -> None:
    result = agent.run({"age": 40, "primary_diagnosis": "Not A Real Disease"})
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_reasoning_lists_contributing_factors(agent: RiskAssessorAgent) -> None:
    result = agent.run({"age": 45, "comorbidities": ["diabetes"], "primary_diagnosis": "Pneumonia"})
    assert "age 45" in result["reasoning"]
    assert "diabetes" in result["reasoning"]
    assert "Pneumonia" in result["reasoning"]
    assert result["risk_level"] in result["reasoning"]


def test_complications_populated_for_critical_risk(agent: RiskAssessorAgent) -> None:
    result = agent.run(
        {
            "age": 80,
            "comorbidities": ["diabetes", "heart disease", "kidney disease"],
            "primary_diagnosis": "Sepsis",
            "severity_indicators": ["SOB"],
        }
    )
    assert len(result["likely_complications"]) > 0
    assert any("hospitalization" in c.lower() for c in result["likely_complications"])


def test_top_risk_factors_capped_at_three(agent: RiskAssessorAgent) -> None:
    result = agent.run(
        {
            "age": 80,
            "comorbidities": ["diabetes", "heart disease", "kidney disease"],
            "primary_diagnosis": "Sepsis",
            "severity_indicators": ["SOB"],
        }
    )
    assert len(result["top_risk_factors"]) <= 3


def test_empty_kb_raises_agent_error() -> None:
    class EmptyKB:
        risk_factors: dict = {}
        conditions: dict = {}

        def normalize_symptom(self, s: str) -> str:
            return s.lower()

    agent = RiskAssessorAgent(kb=EmptyKB())
    with pytest.raises(AgentError):
        agent.run({"age": 45})

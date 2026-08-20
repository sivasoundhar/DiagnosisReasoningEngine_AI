"""Tests for the Recommender agent (Day 5)."""
import pytest

from src.agents.base_agent import AgentError
from src.agents.recommender import RecommenderAgent
from src.knowledge.medical_kb import KnowledgeBase


@pytest.fixture
def agent(knowledge_base: KnowledgeBase) -> RecommenderAgent:
    return RecommenderAgent(kb=knowledge_base)


def test_imports_and_constructs_without_error(agent: RecommenderAgent) -> None:
    assert agent.name == "recommender"


def test_pneumonia_medium_risk_includes_xray_and_antibiotics(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia", "confidence": 75}], "risk_level": "MEDIUM"})
    assert "Chest X-ray" in result["tests"]
    assert "Antibiotic (amoxicillin or azithromycin)" in result["treatments"]


def test_high_risk_adds_hospitalization(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "HIGH"})
    assert any("admission" in t.lower() for t in result["treatments"])
    assert result["setting"] == "inpatient"


def test_critical_risk_adds_icu_admission(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Sepsis"}], "risk_level": "CRITICAL"})
    assert "ICU admission" in result["treatments"]
    assert result["setting"] == "ICU"


def test_multiple_diagnoses_merge_all_recommendations(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}, {"name": "Anemia"}], "risk_level": "MEDIUM"})
    assert "Chest X-ray" in result["tests"]  # from Pneumonia
    assert "Iron studies" in result["tests"]  # from Anemia
    assert "Iron supplementation" in result["treatments"]  # from Anemia


def test_multiple_diagnoses_dedupe_shared_items(agent: RecommenderAgent) -> None:
    # Both Pneumonia and Sepsis recommend CBC - should appear exactly once.
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}, {"name": "Sepsis"}], "risk_level": "MEDIUM"})
    assert result["tests"].count("CBC") == 1


def test_low_risk_is_conservative(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "LOW"})
    assert result["setting"] == "outpatient"
    assert not any("admission" in t.lower() for t in result["treatments"])


def test_unknown_diagnosis_falls_back_gracefully(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Not A Real Disease"}], "risk_level": "MEDIUM"})
    assert "Not A Real Disease" in result["unknown_diagnoses"]
    assert len(result["tests"]) > 0
    assert len(result["treatments"]) > 0


def test_empty_diagnoses_returns_generic_fallback_not_empty(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [], "risk_level": "MEDIUM"})
    assert len(result["tests"]) > 0
    assert len(result["treatments"]) > 0


def test_missing_risk_level_defaults_to_medium(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}]})
    assert result["risk_level_used"] == "MEDIUM"


def test_invalid_risk_level_defaults_to_medium(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "SUPER_HIGH"})
    assert result["risk_level_used"] == "MEDIUM"


def test_elderly_age_adds_extra_tests(agent: RecommenderAgent) -> None:
    young = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "MEDIUM", "age": 30})
    elderly = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "MEDIUM", "age": 80})
    assert "ECG (baseline cardiac assessment)" in elderly["tests"]
    assert "ECG (baseline cardiac assessment)" not in young["tests"]


def test_follow_up_timeline_matches_risk_level(agent: RecommenderAgent) -> None:
    low = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "LOW"})
    critical = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "CRITICAL"})
    assert "1-2 weeks" in low["follow_up"]
    assert "ICU" in critical["follow_up"]


def test_reasoning_summary_explains_each_recommendation(agent: RecommenderAgent) -> None:
    result = agent.run({"diagnoses": [{"name": "Pneumonia"}], "risk_level": "MEDIUM"})
    assert "Chest X-ray" in result["reasoning_summary"]
    assert "infection" in result["reasoning_summary"].lower() or "diagnosis" in result["reasoning_summary"].lower()


def test_empty_kb_raises_agent_error() -> None:
    class EmptyKB:
        conditions: dict = {}
        recommendations: dict = {}

    agent = RecommenderAgent(kb=EmptyKB())
    with pytest.raises(AgentError):
        agent.run({"diagnoses": [{"name": "Pneumonia"}]})

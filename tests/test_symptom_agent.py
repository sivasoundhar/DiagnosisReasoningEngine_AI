"""Tests for the Symptom Analyzer agent (Day 2)."""
import pytest

from src.agents.base_agent import AgentError
from src.agents.symptom_analyzer import SymptomAnalyzerAgent
from src.knowledge.medical_kb import KnowledgeBase


@pytest.fixture
def agent(knowledge_base: KnowledgeBase) -> SymptomAnalyzerAgent:
    return SymptomAnalyzerAgent(kb=knowledge_base)


def test_imports_and_constructs_without_error(agent: SymptomAnalyzerAgent) -> None:
    assert agent.name == "symptom_analyzer"


def test_classic_pneumonia_triad_ranks_pneumonia_in_top_3(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever", "cough", "SOB"]})
    top_3_names = [d["name"] for d in result["diagnoses"][:3]]
    assert "Pneumonia" in top_3_names


def test_pneumonia_confidence_reasonable_for_classic_triad(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever", "cough", "SOB"]})
    pneumonia = next(d for d in result["diagnoses"] if d["name"] == "Pneumonia")
    assert pneumonia["confidence"] >= 60


def test_single_symptom_returns_multiple_diagnoses(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever"]})
    assert len(result["diagnoses"]) >= 2


def test_unknown_symptom_handled_gracefully(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["xyz123"]})
    assert result["diagnoses"] == []
    assert "xyz123" in result["unknown_symptoms"]


def test_empty_symptoms_raises_agent_error(agent: SymptomAnalyzerAgent) -> None:
    with pytest.raises(AgentError):
        agent.run({"symptoms": []})


def test_confidence_scores_within_valid_range(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever", "cough", "SOB", "chest pain"]})
    for diagnosis in result["diagnoses"]:
        assert 0 <= diagnosis["confidence"] <= 100


def test_top_5_limit_enforced(agent: SymptomAnalyzerAgent) -> None:
    # Enough distinct symptoms to spread across well over 5 diagnoses.
    result = agent.run(
        {
            "symptoms": [
                "fever", "cough", "shortness of breath", "chest pain",
                "palpitations", "dizziness", "fatigue",
            ]
        }
    )
    assert len(result["diagnoses"]) <= 5


def test_reasoning_chain_is_readable(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever", "cough", "SOB"]})
    pneumonia = next(d for d in result["diagnoses"] if d["name"] == "Pneumonia")
    assert "fever" in pneumonia["reasoning"]
    assert "cough" in pneumonia["reasoning"]
    assert "SOB" in pneumonia["reasoning"]


def test_mixed_known_and_unknown_symptoms(agent: SymptomAnalyzerAgent) -> None:
    result = agent.run({"symptoms": ["fever", "not_a_real_symptom"]})
    assert len(result["diagnoses"]) >= 1
    assert "not_a_real_symptom" in result["unknown_symptoms"]

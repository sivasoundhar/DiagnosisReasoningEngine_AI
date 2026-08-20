"""Tests for the Lab Interpreter agent."""
import pytest

from src.agents.base_agent import AgentError
from src.agents.lab_interpreter import LabInterpreterAgent
from src.knowledge.medical_kb import KnowledgeBase


@pytest.fixture
def agent(knowledge_base: KnowledgeBase) -> LabInterpreterAgent:
    return LabInterpreterAgent(kb=knowledge_base)


def test_imports_and_constructs_without_error(agent: LabInterpreterAgent) -> None:
    assert agent.name == "lab_interpreter"


def test_elevated_wbc_flags_infection(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 11.2}})
    wbc = result["interpretations"][0]
    assert wbc["status"] == "ELEVATED"
    assert "infection" in wbc["interpretation"].lower()


def test_elevated_crp_flags_inflammation(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"CRP": 8.5}})
    crp = result["interpretations"][0]
    assert crp["status"] == "ELEVATED"
    assert "inflammation" in crp["interpretation"].lower()


def test_all_normal_labs_read_within_limits(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 7.0, "glucose": 90, "hemoglobin": 14.0}})
    assert all(f["status"] == "NORMAL" for f in result["interpretations"])
    assert all("normal" in f["interpretation"].lower() for f in result["interpretations"])


def test_missing_labs_handled_gracefully(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {}})
    assert result["interpretations"] == []
    assert result["unknown_labs"] == []


def test_no_labs_key_handled_gracefully(agent: LabInterpreterAgent) -> None:
    result = agent.run({})
    assert result["interpretations"] == []


def test_normal_wbc_is_not_misclassified_as_low(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 7.0}})
    assert result["interpretations"][0]["status"] == "NORMAL"


def test_unknown_lab_name_skipped_gracefully(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"made_up_lab": 5.0}})
    assert result["interpretations"] == []
    assert "made_up_lab" in result["unknown_labs"]


def test_implausible_value_flagged_as_error(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 5000}})
    finding = result["interpretations"][0]
    assert finding["flagged"] is True
    assert "WBC" in result["flagged_labs"]
    assert finding["confidence"] <= 20


def test_confidence_between_0_and_100(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 11.2, "CRP": 8.5, "glucose": 90}})
    for finding in result["interpretations"]:
        assert 0 <= finding["confidence"] <= 100


def test_supporting_diagnoses_populated_for_abnormal_findings(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 11.2}})
    assert "Pneumonia" in result["supporting_diagnoses"]


def test_supporting_diagnoses_empty_when_all_normal(agent: LabInterpreterAgent) -> None:
    result = agent.run({"labs": {"WBC": 7.0}})
    assert result["supporting_diagnoses"] == []


def test_empty_kb_raises_agent_error() -> None:
    class EmptyKB:
        labs: dict = {}

    agent = LabInterpreterAgent(kb=EmptyKB())
    with pytest.raises(AgentError):
        agent.run({"labs": {"WBC": 11.2}})

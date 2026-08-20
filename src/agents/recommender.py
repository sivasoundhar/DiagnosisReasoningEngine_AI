"""Recommender Agent: diagnoses + risk level -> tests, treatments, and follow-up plan.

Same gather-then-adjust LangGraph shape as the other agents. Per-diagnosis
baselines come from conditions.json; risk-level/age escalation and all
clinical rationale text come from recommendations.json, so nothing clinical
is hardcoded in Python.
"""
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import AgentError, BaseAgent
from src.knowledge.medical_kb import KnowledgeBase

logger = logging.getLogger("diagnosis_engine.agents.recommender")

_VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class RecommenderState(TypedDict, total=False):
    """State threaded through the gather -> adjust graph."""

    diagnoses: list[dict[str, Any]]
    risk_level: str | None
    age: int | None
    tests: list[str]
    treatments: list[str]
    unknown_diagnoses: list[str]
    per_diagnosis_notes: list[dict[str, str]]
    setting: str
    follow_up: str
    reasoning_lines: list[str]


def _extend_unique(target: list[str], items: list[str]) -> None:
    """Append items not already present, preserving order - avoids duplicate recommendations."""
    for item in items:
        if item not in target:
            target.append(item)


class RecommenderAgent(BaseAgent):
    """Turns diagnoses + risk level into a concrete tests/treatments/follow-up plan."""

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        super().__init__(
            name="recommender",
            description="Recommends tests, treatments, and follow-up based on diagnoses and risk level.",
            confidence_threshold=0.0,
        )
        self.kb = kb or KnowledgeBase()
        self.rec_data = self.kb.recommendations
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(RecommenderState)
        graph.add_node("gather_recommendations", self._gather_recommendations_node)
        graph.add_node("apply_adjustments", self._apply_adjustments_node)
        graph.add_edge(START, "gather_recommendations")
        graph.add_edge("gather_recommendations", "apply_adjustments")
        graph.add_edge("apply_adjustments", END)
        return graph.compile()

    def _gather_recommendations_node(self, state: RecommenderState) -> RecommenderState:
        """Look up baseline tests/treatments per diagnosis, merging duplicates across diagnoses."""
        tests: list[str] = []
        treatments: list[str] = []
        unknown_diagnoses: list[str] = []
        per_diagnosis_notes: list[dict[str, str]] = []
        fallback = self.rec_data["unknown_diagnosis_workup"]

        for diagnosis in state["diagnoses"]:
            name = diagnosis.get("name") if isinstance(diagnosis, dict) else diagnosis
            info = self.kb.conditions.get(name)
            if info is None:
                self.logger.warning("Unknown diagnosis '%s' - using generic workup", name)
                unknown_diagnoses.append(name)
                _extend_unique(tests, fallback["tests"])
                _extend_unique(treatments, fallback["treatments"])
                continue
            _extend_unique(tests, info["tests"])
            _extend_unique(treatments, info["treatments"])
            per_diagnosis_notes.append({"name": name, "follow_up": info["follow_up"]})

        if not tests and not treatments:
            # No diagnoses provided, or none resolved to anything usable - never return an
            # empty recommendation, fall back to a generic workup instead.
            self.logger.info("No usable diagnoses for recommendations - applying generic fallback workup")
            _extend_unique(tests, fallback["tests"])
            _extend_unique(treatments, fallback["treatments"])

        return {
            **state,
            "tests": tests,
            "treatments": treatments,
            "unknown_diagnoses": unknown_diagnoses,
            "per_diagnosis_notes": per_diagnosis_notes,
        }

    def _apply_adjustments_node(self, state: RecommenderState) -> RecommenderState:
        """Layer risk-level escalation and elderly-specific tests on top of the baseline."""
        tests = list(state["tests"])
        treatments = list(state["treatments"])

        risk_level = state.get("risk_level")
        default_level = self.rec_data["default_risk_level"]
        if risk_level not in _VALID_RISK_LEVELS:
            if risk_level:
                self.logger.warning("Unrecognized risk level '%s' - defaulting to %s", risk_level, default_level)
            else:
                self.logger.info("No risk level provided - defaulting to %s", default_level)
            risk_level = default_level

        actions = self.rec_data["risk_level_actions"][risk_level]
        _extend_unique(tests, actions["additional_tests"])
        _extend_unique(treatments, actions["additional_treatments"])

        age = state.get("age")
        elderly_threshold = self.rec_data["elderly_age_threshold"]
        if isinstance(age, (int, float)) and age >= elderly_threshold:
            _extend_unique(tests, self.rec_data["elderly_additional_tests"])

        follow_up = self.rec_data["follow_up_by_risk_level"][risk_level]

        test_rationale = self.rec_data["test_rationale"]
        treatment_rationale = self.rec_data["treatment_rationale"]
        reasoning_lines = [
            f"{t}: {test_rationale.get(t, 'Supports diagnostic workup for the suspected condition(s)')}"
            for t in tests
        ] + [
            f"{t}: {treatment_rationale.get(t, 'Addresses the suspected condition(s)')}"
            for t in treatments
        ]

        return {
            **state,
            "tests": tests,
            "treatments": treatments,
            "risk_level": risk_level,
            "setting": actions["setting"],
            "follow_up": follow_up,
            "reasoning_lines": reasoning_lines,
        }

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        if not self.kb.conditions or not self.rec_data:
            raise AgentError("Medical knowledge base is empty - cannot generate recommendations.")

        initial_state: RecommenderState = {
            "diagnoses": input_data.get("diagnoses") or [],
            "risk_level": input_data.get("risk_level"),
            "age": input_data.get("age"),
        }
        return self._graph.invoke(initial_state)

    def get_reasoning(self, result: dict[str, Any]) -> str:
        lines = result.get("reasoning_lines", [])
        return "\n".join(lines) if lines else "No specific recommendations generated."

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "tests": result.get("tests", []),
            "treatments": result.get("treatments", []),
            "follow_up": result.get("follow_up", ""),
            "setting": result.get("setting", ""),
            "risk_level_used": result.get("risk_level", ""),
            "unknown_diagnoses": result.get("unknown_diagnoses", []),
            "per_diagnosis_notes": result.get("per_diagnosis_notes", []),
            "reasoning_summary": self.get_reasoning(result),
        }

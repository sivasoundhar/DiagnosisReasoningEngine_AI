"""Symptom Analyzer Agent: reported symptoms -> ranked differential diagnoses.

Implemented as a small LangGraph pipeline (score -> rank) rather than a single
function so it drops straight into the Day 6 supervisor graph as a node, and
so scoring/ranking can evolve independently (e.g. ranking swapped for an LLM
re-ranker later) without touching the other stage.
"""
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import AgentError, BaseAgent
from src.knowledge.medical_kb import KnowledgeBase

logger = logging.getLogger("diagnosis_engine.agents.symptom_analyzer")

# Scoring weights per Day 2 spec: exact match = +50, partial = +25, indirect link = +10.
_SCORE_WEIGHTS: dict[str, int] = {"exact": 50, "partial": 25, "indirect": 10}
_MATCH_PHRASES: dict[str, str] = {
    "exact": "strong match",
    "partial": "moderate match",
    "indirect": "indirect link",
}
_TOP_N = 5


class SymptomAnalyzerState(TypedDict, total=False):
    """State threaded through the score -> rank graph."""

    symptoms: list[str]
    matched_symptoms: dict[str, list[tuple[str, str]]]  # diagnosis -> [(symptom, match_type), ...]
    raw_scores: dict[str, float]
    unknown_symptoms: list[str]
    diagnoses: list[dict[str, Any]]


class SymptomAnalyzerAgent(BaseAgent):
    """Maps reported symptoms to ranked differential diagnoses via the medical KB."""

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        super().__init__(
            name="symptom_analyzer",
            description="Matches reported symptoms to candidate diagnoses with confidence scoring.",
            confidence_threshold=10.0,
        )
        self.kb = kb or KnowledgeBase()
        self._graph = self._build_graph()

    def _build_graph(self):
        """Two-node graph: score every symptom against the KB, then rank + trim to top N."""
        graph = StateGraph(SymptomAnalyzerState)
        graph.add_node("score_symptoms", self._score_symptoms_node)
        graph.add_node("rank_diagnoses", self._rank_diagnoses_node)
        graph.add_edge(START, "score_symptoms")
        graph.add_edge("score_symptoms", "rank_diagnoses")
        graph.add_edge("rank_diagnoses", END)
        return graph.compile()

    def _score_symptoms_node(self, state: SymptomAnalyzerState) -> SymptomAnalyzerState:
        """Look up each symptom in the KB and accumulate weighted scores per diagnosis."""
        matched: dict[str, list[tuple[str, str]]] = {}
        raw_scores: dict[str, float] = {}
        unknown: list[str] = []

        for symptom in state["symptoms"]:
            candidates = self.kb.get_diagnoses_for_symptom(symptom)
            if not candidates:
                unknown.append(symptom)
                continue
            for candidate in candidates:
                name = candidate["name"]
                weight = _SCORE_WEIGHTS.get(candidate["match"], 0)
                raw_scores[name] = raw_scores.get(name, 0) + weight
                matched.setdefault(name, []).append((symptom, candidate["match"]))

        self.logger.debug(
            "Scored %d symptoms -> %d candidate diagnoses (%d unrecognized: %s)",
            len(state["symptoms"]), len(raw_scores), len(unknown), unknown,
        )
        return {**state, "matched_symptoms": matched, "raw_scores": raw_scores, "unknown_symptoms": unknown}

    def _rank_diagnoses_node(self, state: SymptomAnalyzerState) -> SymptomAnalyzerState:
        """Normalize raw scores to 0-100 (relative to an all-exact-match best case) and take top N."""
        num_symptoms = len(state["symptoms"])
        max_possible = num_symptoms * _SCORE_WEIGHTS["exact"]

        ranked: list[dict[str, Any]] = []
        for name, raw_score in state["raw_scores"].items():
            confidence = round(min(100.0, (raw_score / max_possible) * 100), 1) if max_possible else 0.0
            contributing = state["matched_symptoms"][name]
            reasoning_parts = [
                f"{symptom} ({_MATCH_PHRASES.get(match_type, match_type)})"
                for symptom, match_type in contributing
            ]
            reasoning = f"{name} ({confidence}): " + " + ".join(reasoning_parts)
            ranked.append({"name": name, "confidence": confidence, "reasoning": reasoning})

        ranked.sort(key=lambda d: d["confidence"], reverse=True)
        return {**state, "diagnoses": ranked[:_TOP_N]}

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        symptoms = input_data.get("symptoms")
        if not symptoms:
            raise AgentError(
                "No symptoms provided. Please supply at least one symptom, "
                "e.g. {'symptoms': ['fever', 'cough']}."
            )
        if not self.kb.symptoms:
            # Distinct from "this particular symptom is unrecognized" (handled gracefully below) -
            # this means the KB itself failed to load any data, which is unrecoverable.
            raise AgentError("Medical knowledge base is empty - cannot analyze symptoms.")

        return self._graph.invoke({"symptoms": symptoms})

    def get_reasoning(self, result: dict[str, Any]) -> str:
        diagnoses = result.get("diagnoses", [])
        if not diagnoses:
            return "No matching diagnoses found for the reported symptoms."
        return "\n".join(d["reasoning"] for d in diagnoses)

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "diagnoses": result.get("diagnoses", []),
            "unknown_symptoms": result.get("unknown_symptoms", []),
            "reasoning_summary": self.get_reasoning(result),
        }

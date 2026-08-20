"""Risk Assessor Agent: patient profile -> risk level (LOW/MEDIUM/HIGH/CRITICAL).

Same score-then-classify LangGraph shape as the other agents. All scoring
weights live in knowledge/risk_factors.json, not here, so the clinical
judgment calls are auditable/editable without touching code.
"""
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import AgentError, BaseAgent
from src.knowledge.medical_kb import KnowledgeBase

logger = logging.getLogger("diagnosis_engine.agents.risk_assessor")

_MIN_PLAUSIBLE_AGE = 0
_MAX_PLAUSIBLE_AGE = 120


class RiskAssessorState(TypedDict, total=False):
    """State threaded through the score -> classify graph."""

    age: int | None
    comorbidities: list[str]
    primary_diagnosis: str | None
    severity_indicators: list[str]
    score_breakdown: list[dict[str, Any]]
    total_score: int
    risk_level: str
    top_risk_factors: list[dict[str, Any]]
    complications: list[str]
    reasoning: str


class RiskAssessorAgent(BaseAgent):
    """Scores age + comorbidities + diagnosis severity + severity indicators into a risk level."""

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        super().__init__(
            name="risk_assessor",
            description="Calculates patient risk level from age, comorbidities, diagnosis, and severity signs.",
            confidence_threshold=0.0,
        )
        self.kb = kb or KnowledgeBase()
        self.weights = self.kb.risk_factors
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(RiskAssessorState)
        graph.add_node("calculate_score", self._calculate_score_node)
        graph.add_node("classify_risk", self._classify_risk_node)
        graph.add_edge(START, "calculate_score")
        graph.add_edge("calculate_score", "classify_risk")
        graph.add_edge("classify_risk", END)
        return graph.compile()

    def _points_for_age(self, age: int) -> int:
        for bracket in self.weights["age_brackets"]:
            if bracket["min"] <= age <= bracket["max"]:
                return bracket["points"]
        return self.weights["default_age_points"]

    def _score_age(self, age: int | None, breakdown: list[dict[str, Any]]) -> int:
        default = self.weights["default_age_points"]
        if age is None:
            self.logger.info("No age provided - using default age risk points (%d)", default)
            breakdown.append({"factor": "age: unknown", "points": default})
            return default
        if not (_MIN_PLAUSIBLE_AGE <= age <= _MAX_PLAUSIBLE_AGE):
            self.logger.error("Invalid age %s (outside 0-120) - using default age risk points", age)
            breakdown.append({"factor": f"age: {age} (invalid, default applied)", "points": default})
            return default
        points = self._points_for_age(age)
        breakdown.append({"factor": f"age {age}", "points": points})
        return points

    def _score_comorbidities(self, comorbidities: list[str], breakdown: list[dict[str, Any]]) -> int:
        total = 0
        for name in comorbidities:
            points = self.weights["comorbidity_points"].get(name.strip().lower())
            if points is None:
                self.logger.warning("Unknown comorbidity '%s' - skipping", name)
                continue
            breakdown.append({"factor": f"comorbidity: {name}", "points": points})
            total += points
        return total

    def _score_diagnosis(self, diagnosis: str | None, breakdown: list[dict[str, Any]]) -> int:
        if not diagnosis:
            return 0
        info = self.kb.conditions.get(diagnosis)
        if info is None:
            points = self.weights["default_severity_points"]
            self.logger.warning("Unknown diagnosis '%s' - using generic severity score (%d)", diagnosis, points)
        else:
            points = self.weights["severity_points"].get(info["severity"], self.weights["default_severity_points"])
        breakdown.append({"factor": f"diagnosis: {diagnosis}", "points": points})
        return points

    def _score_severity_indicators(self, indicators: list[str], breakdown: list[dict[str, Any]]) -> int:
        total = 0
        for indicator in indicators:
            key = self.kb.normalize_symptom(indicator)
            points = self.weights["severity_indicator_points"].get(key)
            if points is None:
                self.logger.warning("Unrecognized severity indicator '%s' - skipping", indicator)
                continue
            breakdown.append({"factor": f"severity indicator: {indicator}", "points": points})
            total += points
        return total

    def _calculate_score_node(self, state: RiskAssessorState) -> RiskAssessorState:
        breakdown: list[dict[str, Any]] = []
        total = 0
        total += self._score_age(state.get("age"), breakdown)
        total += self._score_comorbidities(state.get("comorbidities", []), breakdown)
        total += self._score_diagnosis(state.get("primary_diagnosis"), breakdown)
        total += self._score_severity_indicators(state.get("severity_indicators", []), breakdown)
        self.logger.debug("Risk score breakdown: %s (total=%d)", breakdown, total)
        return {**state, "score_breakdown": breakdown, "total_score": total}

    def _level_for_score(self, score: int) -> str:
        for threshold in self.weights["risk_level_thresholds"]:
            if score <= threshold["max"]:
                return threshold["level"]
        return self.weights["risk_level_thresholds"][-1]["level"]

    def _classify_risk_node(self, state: RiskAssessorState) -> RiskAssessorState:
        breakdown = state["score_breakdown"]
        total = state["total_score"]
        level = self._level_for_score(total)
        complications = self.weights["complications_by_level"].get(level, [])
        top_factors = sorted(breakdown, key=lambda f: f["points"], reverse=True)[:3]

        factors_str = " + ".join(f["factor"] for f in breakdown) or "no risk factors identified"
        reasoning = f"{factors_str} = {level} ({total} points)"

        return {
            **state,
            "risk_level": level,
            "complications": complications,
            "top_risk_factors": top_factors,
            "reasoning": reasoning,
        }

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        if not self.weights:
            raise AgentError("Risk factor knowledge base is empty - cannot assess risk.")

        initial_state: RiskAssessorState = {
            "age": input_data.get("age"),
            "comorbidities": input_data.get("comorbidities") or [],
            "primary_diagnosis": input_data.get("primary_diagnosis"),
            "severity_indicators": input_data.get("severity_indicators") or [],
        }
        return self._graph.invoke(initial_state)

    def get_reasoning(self, result: dict[str, Any]) -> str:
        return result.get("reasoning", "")

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "risk_level": result["risk_level"],
            "score": result["total_score"],
            "reasoning": self.get_reasoning(result),
            "top_risk_factors": result.get("top_risk_factors", []),
            "likely_complications": result.get("complications", []),
            "score_breakdown": result.get("score_breakdown", []),
        }

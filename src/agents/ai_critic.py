"""AI Critic Agent (Day 13): an LLM cross-check of the rule-based result.

The Day 12 AI Reasoner produces an *independent* second opinion - it never sees the rule
engine's output, by design, so it can't rubber-stamp it. This agent does the opposite job on
purpose: it's shown the rule-based `diagnoses`/`risk_assessment`/`recommendation` (plus the
original case for context) and asked to actually critique that result - flag concerns, name
anything clinically important the rule engine may have missed, and give an overall
agrees/partially_agrees/disagrees assessment with reasoning.

This is the actual "cross-verification" step: Symptom Analyzer/Lab Interpreter/Risk
Assessor/Recommender compute a result, AI Reasoner independently forms its own opinion, and
*this* agent is the one that reviews the rule engine's specific output and says whether it holds
up. Like AI Reasoner, it's supplementary - `ai_critique` is surfaced separately on
`DiagnosisOutput`, never used to alter the rule-based result itself, and is `None` when no LLM is
configured or the call fails (same degrade-gracefully pattern as every other optional stage).
"""
import logging
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from src.agents.base_agent import AgentError, BaseAgent

logger = logging.getLogger("diagnosis_engine.agents.ai_critic")

_SYSTEM_PROMPT = (
    "You are a careful clinical reviewer cross-checking another system's diagnostic reasoning. "
    "You will be given a patient's case (age, symptoms, comorbidities, labs) and a rule-based "
    "clinical decision-support system's output: its top differential diagnoses, risk assessment, "
    "and recommended workup. Critically review that output against the case: is the top diagnosis "
    "well-supported? Is anything clinically important missing from the differential, the risk "
    "assessment, or the recommended tests/treatments? Give an overall assessment - 'agrees' if the "
    "result looks sound, 'partially_agrees' if it's reasonable but has gaps, or 'disagrees' if you "
    "think it's meaningfully wrong or missing something important - plus concrete concerns (if "
    "any), any missed considerations (if any), and a short narrative explaining your assessment. "
    "This is an educational/research decision-support tool, not a medical device - never claim "
    "certainty."
)

_VALID_ASSESSMENTS = {"agrees", "partially_agrees", "disagrees"}
_DEFAULT_ASSESSMENT = "partially_agrees"


class AICritiqueSchema(BaseModel):
    """Structured output contract the LLM must fill in (used via `with_structured_output`)."""

    assessment: str = Field(..., description="One of: agrees, partially_agrees, disagrees")
    concerns: list[str] = Field(default_factory=list, description="Specific issues with the rule-based result, if any")
    missed_considerations: list[str] = Field(
        default_factory=list, description="Clinically relevant things the rule-based result didn't consider, if any"
    )
    narrative: str = Field(..., description="2-4 sentence explanation of the overall assessment")


class AICriticState(TypedDict, total=False):
    """State threaded through the build-review-context -> call-LLM graph."""

    symptoms: list[str]
    labs: dict[str, float]
    age: int | None
    comorbidities: list[str]
    diagnoses: list[dict[str, Any]]
    risk_assessment: dict[str, Any] | None
    recommendation: dict[str, Any] | None
    review_context: str
    assessment: str
    concerns: list[str]
    missed_considerations: list[str]
    narrative: str
    model_used: str


class AICriticAgent(BaseAgent):
    """Calls an LLM to critique the rule-based pipeline's own result.

    `llm` is dependency-injected, same pattern as `AIReasonerAgent` - tests supply a fake and
    never touch the network; `llm=None` means "no LLM configured" and `invoke()` raises
    AgentError rather than crashing.
    """

    def __init__(self, llm: Any = None, model_name: str = "") -> None:
        super().__init__(
            name="ai_critic",
            description="LLM cross-check of the rule-based diagnosis/risk/recommendation result.",
            confidence_threshold=0.0,
        )
        self._llm = llm
        self._model_name = model_name
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AICriticState)
        graph.add_node("build_review_context", self._build_review_context_node)
        graph.add_node("call_llm", self._call_llm_node)
        graph.add_edge(START, "build_review_context")
        graph.add_edge("build_review_context", "call_llm")
        graph.add_edge("call_llm", END)
        return graph.compile()

    def _build_review_context_node(self, state: AICriticState) -> AICriticState:
        """Turn the case + rule-based result into plain English for the LLM to review."""
        symptoms = state.get("symptoms") or []
        comorbidities = state.get("comorbidities") or []
        labs = state.get("labs") or {}
        diagnoses = state.get("diagnoses") or []
        risk = state.get("risk_assessment")
        rec = state.get("recommendation")

        lines = [
            "Patient case:",
            f"  Age: {state.get('age') if state.get('age') is not None else 'unknown'}",
            f"  Symptoms: {', '.join(symptoms) if symptoms else 'none reported'}",
            f"  Comorbidities: {', '.join(comorbidities) if comorbidities else 'none reported'}",
        ]
        if labs:
            lines.append("  Labs: " + ", ".join(f"{name}={value}" for name, value in labs.items()))

        lines.append("\nRule-based system's result:")
        if diagnoses:
            lines.append(
                "  Differential diagnosis: "
                + "; ".join(f"{d.get('name')} ({d.get('confidence')}%)" for d in diagnoses)
            )
        else:
            lines.append("  Differential diagnosis: none produced")
        if risk:
            lines.append(f"  Risk assessment: {risk.get('risk_level')} (score {risk.get('score')}) - {risk.get('reasoning')}")
        else:
            lines.append("  Risk assessment: none produced")
        if rec:
            lines.append(f"  Recommended tests: {', '.join(rec.get('tests', [])) or 'none'}")
            lines.append(f"  Recommended treatments: {', '.join(rec.get('treatments', [])) or 'none'}")
            lines.append(f"  Follow-up: {rec.get('follow_up', 'none')}")
        else:
            lines.append("  Recommendation: none produced")

        return {**state, "review_context": "\n".join(lines)}

    def _call_llm_node(self, state: AICriticState) -> AICriticState:
        if self._llm is None:
            raise AgentError("No LLM configured (GROQ_API_KEY unset) - AI Critic agent is unavailable.")

        structured_llm = self._llm.with_structured_output(AICritiqueSchema)
        try:
            critique: AICritiqueSchema = structured_llm.invoke(
                [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=state["review_context"])]
            )
        except Exception as exc:  # noqa: BLE001 - any Groq/network/parsing failure becomes an AgentError
            raise AgentError(f"LLM call failed: {exc}") from exc

        assessment = critique.assessment.strip().lower()
        if assessment not in _VALID_ASSESSMENTS:
            self.logger.warning("Unrecognized assessment '%s' from LLM - defaulting to %s", assessment, _DEFAULT_ASSESSMENT)
            assessment = _DEFAULT_ASSESSMENT

        return {
            **state,
            "assessment": assessment,
            "concerns": critique.concerns,
            "missed_considerations": critique.missed_considerations,
            "narrative": critique.narrative,
            "model_used": self._model_name,
        }

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        initial_state: AICriticState = {
            "symptoms": input_data.get("symptoms") or [],
            "labs": input_data.get("labs") or {},
            "age": input_data.get("age"),
            "comorbidities": input_data.get("comorbidities") or [],
            "diagnoses": input_data.get("diagnoses") or [],
            "risk_assessment": input_data.get("risk_assessment"),
            "recommendation": input_data.get("recommendation"),
        }
        return self._graph.invoke(initial_state)

    def get_reasoning(self, result: dict[str, Any]) -> str:
        return result.get("narrative") or "No AI critique produced."

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "assessment": result.get("assessment", _DEFAULT_ASSESSMENT),
            "concerns": result.get("concerns", []),
            "missed_considerations": result.get("missed_considerations", []),
            "narrative": result.get("narrative", ""),
            "model": result.get("model_used", ""),
        }

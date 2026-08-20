"""AI Reasoning Agent (Day 12): a genuine LLM-based independent second opinion.

Every other agent (Days 2-5) is deterministic and KB-driven on purpose - the
auditable core of this app, and it stays that way. This agent is different by
design: it calls an LLM (Groq) to reason over the same raw case the Symptom
Analyzer sees - symptoms, labs, age, comorbidities - and produces its own
differential diagnosis and narrative reasoning.

Two things keep this safe and honest rather than just bolted-on marketing:

1. **Genuine independence.** This agent only ever receives the original
   patient input, never the rule engine's `diagnoses`/`risk_assessment`/
   `recommendation`. It can't rubber-stamp an answer it was shown - it has to
   actually reason. (See `supervisor.py`: `_run_ai_reasoner` reads only
   state["symptoms"/"labs"/"age"/"comorbidities"].)
2. **Never the sole voice.** The API surfaces this as `ai_opinion`, clearly
   separate from `diagnoses` - a supplementary second opinion a clinician can
   compare against the auditable rule-based result, not a replacement for it.
   If no GROQ_API_KEY is configured, or the call fails, the pipeline degrades
   gracefully (`ai_opinion: null`) rather than failing the whole analysis -
   see supervisor.py's degrade-gracefully pattern, same as Lab Interpreter.
"""
import logging
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from src.agents.base_agent import AgentError, BaseAgent

logger = logging.getLogger("diagnosis_engine.agents.ai_reasoner")

_SYSTEM_PROMPT = (
    "You are an independent clinical reasoning assistant helping a clinician think through a "
    "case. Given a patient's age, reported symptoms, comorbidities, and lab values, provide your "
    "own differential diagnosis and reasoning - as if you had not seen any other analysis of this "
    "case. List up to 5 candidate conditions, most likely first, each with a 0-100 confidence and "
    "a one-to-two sentence clinical rationale. Also give a short (2-4 sentence) overall clinical "
    "impression, and flag any urgent/red-flag findings. Be concise and clinically grounded. This "
    "is an educational/research decision-support tool, not a medical device - never claim "
    "certainty, and do not recommend a specific drug dose."
)

_MAX_DIAGNOSES = 5


class AIOpinionDiagnosis(BaseModel):
    """One candidate diagnosis as the LLM structures it."""

    name: str = Field(..., description="Condition name")
    confidence: float = Field(..., ge=0, le=100, description="0-100 confidence")
    reasoning: str = Field(..., description="Why this condition fits, one or two sentences")


class AIOpinionSchema(BaseModel):
    """Structured output contract the LLM must fill in (used via `with_structured_output`)."""

    diagnoses: list[AIOpinionDiagnosis] = Field(..., description="Up to 5 differential diagnoses, most likely first")
    summary: str = Field(..., description="2-4 sentence overall clinical impression")
    red_flags: list[str] = Field(default_factory=list, description="Any urgent/red-flag findings worth flagging")


class AIReasonerState(TypedDict, total=False):
    """State threaded through the summarize -> call-LLM graph."""

    symptoms: list[str]
    labs: dict[str, float]
    age: int | None
    comorbidities: list[str]
    case_summary: str
    ai_diagnoses: list[dict[str, Any]]
    ai_summary: str
    red_flags: list[str]
    model_used: str


class AIReasonerAgent(BaseAgent):
    """Calls an LLM to independently reason over the raw patient case.

    `llm` is dependency-injected (a LangChain chat model exposing
    `with_structured_output`, e.g. `ChatGroq`) rather than built from settings
    inside this class, so tests can supply a fake and never hit the network -
    same dependency-injection pattern the other agents use for `kb`. Pass
    `llm=None` (the default) to represent "no LLM configured" explicitly;
    `invoke()` then raises AgentError rather than crashing on a None call.
    """

    def __init__(self, llm: Any = None, model_name: str = "") -> None:
        super().__init__(
            name="ai_reasoner",
            description="Independent LLM-based second opinion on the differential diagnosis.",
            confidence_threshold=0.0,
        )
        self._llm = llm
        self._model_name = model_name
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AIReasonerState)
        graph.add_node("build_case_summary", self._build_case_summary_node)
        graph.add_node("call_llm", self._call_llm_node)
        graph.add_edge(START, "build_case_summary")
        graph.add_edge("build_case_summary", "call_llm")
        graph.add_edge("call_llm", END)
        return graph.compile()

    def _build_case_summary_node(self, state: AIReasonerState) -> AIReasonerState:
        """Turn the structured input into a plain-English case for the LLM to reason over."""
        symptoms = state.get("symptoms") or []
        comorbidities = state.get("comorbidities") or []
        labs = state.get("labs") or {}

        lines = [
            f"Age: {state.get('age') if state.get('age') is not None else 'unknown'}",
            f"Symptoms: {', '.join(symptoms) if symptoms else 'none reported'}",
            f"Comorbidities: {', '.join(comorbidities) if comorbidities else 'none reported'}",
        ]
        if labs:
            lines.append("Labs: " + ", ".join(f"{name}={value}" for name, value in labs.items()))
        return {**state, "case_summary": "\n".join(lines)}

    def _call_llm_node(self, state: AIReasonerState) -> AIReasonerState:
        if self._llm is None:
            raise AgentError("No LLM configured (GROQ_API_KEY unset) - AI reasoning agent is unavailable.")

        structured_llm = self._llm.with_structured_output(AIOpinionSchema)
        try:
            opinion: AIOpinionSchema = structured_llm.invoke(
                [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=state["case_summary"])]
            )
        except Exception as exc:  # noqa: BLE001 - any Groq/network/parsing failure becomes an AgentError
            raise AgentError(f"LLM call failed: {exc}") from exc

        return {
            **state,
            "ai_diagnoses": [d.model_dump() for d in opinion.diagnoses[:_MAX_DIAGNOSES]],
            "ai_summary": opinion.summary,
            "red_flags": opinion.red_flags,
            "model_used": self._model_name,
        }

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        initial_state: AIReasonerState = {
            "symptoms": input_data.get("symptoms") or [],
            "labs": input_data.get("labs") or {},
            "age": input_data.get("age"),
            "comorbidities": input_data.get("comorbidities") or [],
        }
        return self._graph.invoke(initial_state)

    def get_reasoning(self, result: dict[str, Any]) -> str:
        return result.get("ai_summary") or "No AI reasoning produced."

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "diagnoses": result.get("ai_diagnoses", []),
            "summary": result.get("ai_summary", ""),
            "red_flags": result.get("red_flags", []),
            "model": result.get("model_used", ""),
        }


def default_groq_llm(api_key: str, model: str) -> Any:
    """Build the real Groq client, or None if no API key is configured.

    Kept as a standalone factory (rather than inside `AIReasonerAgent.__init__`)
    so the supervisor decides whether a real client exists, and agent tests
    never need `ChatGroq`/network access at all - they inject a fake `llm`
    directly. Imports `ChatGroq` lazily so importing this module never
    requires the `langchain-groq` package unless an API key is actually set.
    """
    if not api_key:
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(model=model, api_key=api_key, temperature=0.2)

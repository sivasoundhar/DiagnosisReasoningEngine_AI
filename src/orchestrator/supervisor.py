"""Supervisor: LangGraph orchestration wiring the agents into one pipeline.

Sequential order per spec: Symptom Analyzer -> Lab Interpreter -> Risk Assessor ->
Recommender. Each agent already has its own internal two-node graph; this
outer graph treats each agent as a single node, calling `BaseAgent.run()` so logging
and error handling stay uniform with how each agent already behaves standalone.

A 5th node, AI Reasoner, runs after Recommender. It deliberately reads only
the *original* input state (symptoms/labs/age/comorbidities) - never the rule engine's
diagnoses/risk/recommendation - so its opinion is genuinely independent, not primed by
the deterministic result it runs alongside. See `src/agents/ai_reasoner.py`.

A 6th node, AI Critic, runs after AI Reasoner. It does the opposite job on purpose:
it *is* shown the rule engine's diagnoses/risk/recommendation and asked to critique that
specific result (concerns, missed considerations, an agrees/partially_agrees/disagrees
verdict) - this is the actual cross-verification step, distinct from AI Reasoner's
independent opinion. See `src/agents/ai_critic.py`.
"""
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.ai_critic import AICriticAgent
from src.agents.ai_reasoner import AIReasonerAgent, default_groq_llm
from src.agents.base_agent import AgentError
from src.agents.lab_interpreter import LabInterpreterAgent
from src.agents.recommender import RecommenderAgent
from src.agents.risk_assessor import RiskAssessorAgent
from src.agents.symptom_analyzer import SymptomAnalyzerAgent
from src.config import get_settings
from src.knowledge.medical_kb import KnowledgeBase

logger = logging.getLogger("diagnosis_engine.orchestrator.supervisor")


class SupervisorState(TypedDict, total=False):
    """State threaded through the full 4-agent pipeline."""

    # Input (mirrors PatientInput)
    symptoms: list[str]
    labs: dict[str, float]
    age: int | None
    comorbidities: list[str]

    # Per-agent outputs
    diagnoses: list[dict[str, Any]]
    unknown_symptoms: list[str]
    lab_interpretations: list[dict[str, Any]]
    unknown_labs: list[str]
    flagged_labs: list[str]
    risk_assessment: dict[str, Any] | None
    recommendation: dict[str, Any] | None
    ai_opinion: dict[str, Any] | None
    ai_critique: dict[str, Any] | None

    # Diagnostics - which stages, if any, degraded rather than a hard failure
    errors: list[dict[str, str]]


class SupervisorError(AgentError):
    """Raised when the pipeline cannot produce a usable result at all.

    Distinct from a downstream agent degrading gracefully (logged into
    state["errors"] while the pipeline still returns a result): this means
    the foundational step (Symptom Analyzer) itself failed, so there is
    nothing meaningful left to hand to Lab/Risk/Recommender.
    """


class DiagnosisSupervisor:
    """Orchestrates Symptom Analyzer -> Lab Interpreter -> Risk Assessor -> Recommender ->
    AI Reasoner -> AI Critic.

    Owns a single shared KnowledgeBase instance passed to the 4 rule-based agents, so the
    KB JSON is loaded once per supervisor instead of once per agent, and a single shared
    Groq client passed to both LLM agents (AI Reasoner, AI Critic) by default.
    """

    def __init__(self, kb: KnowledgeBase | None = None, ai_reasoner: Any = None, ai_critic: Any = None) -> None:
        self.kb = kb or KnowledgeBase()
        self.symptom_analyzer = SymptomAnalyzerAgent(kb=self.kb)
        self.lab_interpreter = LabInterpreterAgent(kb=self.kb)
        self.risk_assessor = RiskAssessorAgent(kb=self.kb)
        self.recommender = RecommenderAgent(kb=self.kb)
        if ai_reasoner is None or ai_critic is None:
            settings = get_settings()
            # One shared Groq client for both LLM agents - ChatGroq is a stateless per-call
            # client, so there's no reason to open two connections for one API key.
            llm = default_groq_llm(settings.groq_api_key, settings.groq_model)
            ai_reasoner = ai_reasoner or AIReasonerAgent(llm=llm, model_name=settings.groq_model)
            ai_critic = ai_critic or AICriticAgent(llm=llm, model_name=settings.groq_model)
        self.ai_reasoner = ai_reasoner
        self.ai_critic = ai_critic
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(SupervisorState)
        graph.add_node("symptom_analyzer", self._run_symptom_analyzer)
        graph.add_node("lab_interpreter", self._run_lab_interpreter)
        graph.add_node("risk_assessor", self._run_risk_assessor)
        graph.add_node("recommender", self._run_recommender)
        graph.add_node("ai_reasoner", self._run_ai_reasoner)
        graph.add_node("ai_critic", self._run_ai_critic)
        graph.add_edge(START, "symptom_analyzer")
        graph.add_edge("symptom_analyzer", "lab_interpreter")
        graph.add_edge("lab_interpreter", "risk_assessor")
        graph.add_edge("risk_assessor", "recommender")
        graph.add_edge("recommender", "ai_reasoner")
        graph.add_edge("ai_reasoner", "ai_critic")
        graph.add_edge("ai_critic", END)
        return graph.compile()

    def _record_error(self, state: SupervisorState, stage: str, exc: Exception) -> list[dict[str, str]]:
        errors = list(state.get("errors", []))
        errors.append({"stage": stage, "message": str(exc)})
        logger.error("Supervisor stage '%s' degraded: %s", stage, exc)
        return errors

    def _run_symptom_analyzer(self, state: SupervisorState) -> SupervisorState:
        """Foundational step - a failure here means there's nothing to diagnose, so it aborts the pipeline."""
        try:
            result = self.symptom_analyzer.run({"symptoms": state["symptoms"]})
        except AgentError as exc:
            raise SupervisorError(f"Symptom analysis failed, cannot continue: {exc}") from exc
        return {
            **state,
            "diagnoses": result["diagnoses"],
            "unknown_symptoms": result["unknown_symptoms"],
        }

    def _run_lab_interpreter(self, state: SupervisorState) -> SupervisorState:
        """Labs are optional - a failure here degrades to an empty panel, not a pipeline abort."""
        try:
            result = self.lab_interpreter.run({"labs": state.get("labs", {})})
        except AgentError as exc:
            errors = self._record_error(state, "lab_interpreter", exc)
            return {**state, "lab_interpretations": [], "unknown_labs": [], "flagged_labs": [], "errors": errors}
        return {
            **state,
            "lab_interpretations": result["interpretations"],
            "unknown_labs": result["unknown_labs"],
            "flagged_labs": result["flagged_labs"],
        }

    @staticmethod
    def _top_diagnosis(state: SupervisorState) -> str | None:
        diagnoses = state.get("diagnoses") or []
        return diagnoses[0]["name"] if diagnoses else None

    def _run_risk_assessor(self, state: SupervisorState) -> SupervisorState:
        """A failure here degrades to no risk assessment - the Recommender defaults risk to MEDIUM."""
        try:
            result = self.risk_assessor.run(
                {
                    "age": state.get("age"),
                    "comorbidities": state.get("comorbidities", []),
                    "primary_diagnosis": self._top_diagnosis(state),
                    # Reuse reported symptoms as candidate severity indicators (SOB, chest pain,
                    # confusion, hypotension) - PatientInput has no separate field for these, and
                    # the agent already skips anything it doesn't recognize without complaint.
                    "severity_indicators": state.get("symptoms", []),
                }
            )
        except AgentError as exc:
            errors = self._record_error(state, "risk_assessor", exc)
            return {**state, "risk_assessment": None, "errors": errors}
        return {**state, "risk_assessment": result}

    def _run_recommender(self, state: SupervisorState) -> SupervisorState:
        """A failure here still returns diagnoses/risk - only the recommendation itself is dropped."""
        risk_assessment = state.get("risk_assessment")
        try:
            result = self.recommender.run(
                {
                    "diagnoses": state.get("diagnoses", []),
                    "risk_level": risk_assessment["risk_level"] if risk_assessment else None,
                    "age": state.get("age"),
                }
            )
        except AgentError as exc:
            errors = self._record_error(state, "recommender", exc)
            return {**state, "recommendation": None, "errors": errors}
        return {**state, "recommendation": result}

    def _run_ai_reasoner(self, state: SupervisorState) -> SupervisorState:
        """Independent LLM second opinion - reads only the original patient input, never the
        rule engine's diagnoses/risk/recommendation, so it's a genuine independent take rather
        than a rubber stamp. A failure here (e.g. no GROQ_API_KEY configured, or the Groq call
        itself fails) degrades to no AI opinion, same as any other optional stage - the
        rule-based result alone is already a complete, usable answer."""
        try:
            result = self.ai_reasoner.run(
                {
                    "symptoms": state.get("symptoms", []),
                    "labs": state.get("labs", {}),
                    "age": state.get("age"),
                    "comorbidities": state.get("comorbidities", []),
                }
            )
        except AgentError as exc:
            errors = self._record_error(state, "ai_reasoner", exc)
            return {**state, "ai_opinion": None, "errors": errors}
        return {**state, "ai_opinion": result}

    def _run_ai_critic(self, state: SupervisorState) -> SupervisorState:
        """Cross-verification step - unlike AI Reasoner, this one IS shown the rule engine's
        diagnoses/risk/recommendation and asked to critique that specific result. A failure here
        (no GROQ_API_KEY, network, etc.) degrades to no critique, same as every other optional
        stage - the rule-based result and the independent AI opinion are both already complete
        without it."""
        try:
            result = self.ai_critic.run(
                {
                    "symptoms": state.get("symptoms", []),
                    "labs": state.get("labs", {}),
                    "age": state.get("age"),
                    "comorbidities": state.get("comorbidities", []),
                    "diagnoses": state.get("diagnoses", []),
                    "risk_assessment": state.get("risk_assessment"),
                    "recommendation": state.get("recommendation"),
                }
            )
        except AgentError as exc:
            errors = self._record_error(state, "ai_critic", exc)
            return {**state, "ai_critique": None, "errors": errors}
        return {**state, "ai_critique": result}

    def run(self, patient_data: dict[str, Any]) -> dict[str, Any]:
        """Run the full pipeline. `patient_data` mirrors PatientInput: symptoms/labs/age/comorbidities.

        Raises SupervisorError if symptom analysis itself fails (e.g. no symptoms given).
        Any other stage that fails degrades gracefully - its output is None/empty and the
        failure is recorded in the returned `errors` list rather than crashing the pipeline.
        """
        initial_state: SupervisorState = {
            "symptoms": patient_data.get("symptoms") or [],
            "labs": patient_data.get("labs") or {},
            "age": patient_data.get("age"),
            "comorbidities": patient_data.get("comorbidities") or [],
            "errors": [],
        }
        final_state = self._graph.invoke(initial_state)
        return {
            "diagnoses": final_state.get("diagnoses", []),
            "lab_interpretations": final_state.get("lab_interpretations", []),
            "risk_assessment": final_state.get("risk_assessment"),
            "recommendation": final_state.get("recommendation"),
            "ai_opinion": final_state.get("ai_opinion"),
            "ai_critique": final_state.get("ai_critique"),
            "unknown_symptoms": final_state.get("unknown_symptoms", []),
            "unknown_labs": final_state.get("unknown_labs", []),
            "flagged_labs": final_state.get("flagged_labs", []),
            "errors": final_state.get("errors", []),
        }

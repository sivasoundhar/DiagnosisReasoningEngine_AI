"""Lab Interpreter Agent: raw lab values -> clinical interpretation + linked diagnoses.

Same two-stage LangGraph shape as the Symptom Analyzer (interpret each finding,
then aggregate) so both agents plug into the outer supervisor the same way.
"""
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import AgentError, BaseAgent
from src.knowledge.medical_kb import KnowledgeBase

logger = logging.getLogger("diagnosis_engine.agents.lab_interpreter")


class LabInterpreterState(TypedDict, total=False):
    """State threaded through the interpret -> aggregate graph."""

    labs: dict[str, float]
    interpretations: list[dict[str, Any]]
    unknown_labs: list[str]
    flagged_labs: list[str]  # physiologically implausible values - likely data errors
    supporting_diagnoses: list[str]


class LabInterpreterAgent(BaseAgent):
    """Interprets a panel of lab values against KB reference ranges."""

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        super().__init__(
            name="lab_interpreter",
            description="Interprets lab values against reference ranges and links them to diagnoses.",
            confidence_threshold=15.0,
        )
        self.kb = kb or KnowledgeBase()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(LabInterpreterState)
        graph.add_node("interpret_labs", self._interpret_labs_node)
        graph.add_node("aggregate_findings", self._aggregate_findings_node)
        graph.add_edge(START, "interpret_labs")
        graph.add_edge("interpret_labs", "aggregate_findings")
        graph.add_edge("aggregate_findings", END)
        return graph.compile()

    def _certainty_for(self, kb_result: dict[str, Any]) -> int:
        """Well-characterized findings score high; generic-fallback or implausible ones score low."""
        if kb_result["physiologically_implausible"]:
            return 15
        if kb_result["status"] == "NORMAL":
            return 100
        return 90 if kb_result["has_specific_guidance"] else 55

    def _interpret_labs_node(self, state: LabInterpreterState) -> LabInterpreterState:
        interpretations: list[dict[str, Any]] = []
        unknown: list[str] = []
        flagged: list[str] = []

        for lab_name, value in state["labs"].items():
            kb_result = self.kb.interpret_lab(lab_name, value)
            if kb_result is None:
                unknown.append(lab_name)
                continue

            if kb_result["physiologically_implausible"]:
                flagged.append(lab_name)
                self.logger.warning(
                    "Lab '%s' value %s is physiologically implausible - flagging as possible data error",
                    lab_name, value,
                )

            interpretations.append(
                {
                    "lab_name": lab_name,
                    "value": value,
                    "status": kb_result["status"],
                    "interpretation": kb_result["interpretation"],
                    "confidence": self._certainty_for(kb_result),
                    "linked_diagnoses": kb_result["linked_diagnoses"],
                    "flagged": kb_result["physiologically_implausible"],
                }
            )

        self.logger.debug(
            "Interpreted %d labs (%d unrecognized, %d flagged)",
            len(interpretations), len(unknown), len(flagged),
        )
        return {**state, "interpretations": interpretations, "unknown_labs": unknown, "flagged_labs": flagged}

    def _aggregate_findings_node(self, state: LabInterpreterState) -> LabInterpreterState:
        """Collect diagnoses supported by any abnormal (non-normal, non-flagged) finding."""
        supporting: list[str] = []
        for finding in state["interpretations"]:
            if finding["status"] == "NORMAL" or finding["flagged"]:
                continue
            for diagnosis in finding["linked_diagnoses"]:
                if diagnosis not in supporting:
                    supporting.append(diagnosis)
        return {**state, "supporting_diagnoses": supporting}

    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        labs = input_data.get("labs") or {}
        if not self.kb.labs:
            raise AgentError("Medical knowledge base is empty - cannot interpret labs.")

        # No labs provided is a valid, expected case (labs are optional on PatientInput) -
        # return an empty-but-successful result rather than erroring.
        if not labs:
            self.logger.info("No lab values provided - returning empty interpretation")
            return {"interpretations": [], "unknown_labs": [], "flagged_labs": [], "supporting_diagnoses": []}

        return self._graph.invoke({"labs": labs})

    def get_reasoning(self, result: dict[str, Any]) -> str:
        interpretations = result.get("interpretations", [])
        if not interpretations:
            return "No lab values were provided to interpret."
        lines = [
            f"{f['lab_name']}: {f['status']} - {f['interpretation']} (confidence {f['confidence']})"
            for f in interpretations
        ]
        return "\n".join(lines)

    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "interpretations": result.get("interpretations", []),
            "unknown_labs": result.get("unknown_labs", []),
            "flagged_labs": result.get("flagged_labs", []),
            "supporting_diagnoses": result.get("supporting_diagnoses", []),
            "reasoning_summary": self.get_reasoning(result),
        }

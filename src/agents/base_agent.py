"""Abstract base class every LangGraph agent inherits from.

Forcing a shared shape (invoke / get_reasoning / format_output) means the
supervisor (Day 6) can wire all four agents identically, and every agent
is required to explain itself — not just return an answer.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any


class AgentError(Exception):
    """Raised when an agent cannot produce a usable result.

    Distinct from a bare Exception so the supervisor can catch agent
    failures specifically and decide how to degrade gracefully, instead
    of masking unrelated bugs.
    """


class BaseAgent(ABC):
    """Common contract for Symptom Analyzer, Lab Interpreter, Risk Assessor, Recommender."""

    def __init__(self, name: str, description: str, confidence_threshold: float = 0.0) -> None:
        self.name = name
        self.description = description
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(f"diagnosis_engine.agents.{name}")

    @abstractmethod
    def invoke(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the agent's core logic and return a result dict.

        Implementations must validate input_data themselves and raise
        AgentError on unrecoverable problems — never fail silently.
        """
        raise NotImplementedError

    @abstractmethod
    def get_reasoning(self, result: dict[str, Any]) -> str:
        """Return a human-readable explanation of how `result` was reached.

        Clinical users need to trust the output, so every agent must be
        able to explain itself in plain language, not just emit a score.
        """
        raise NotImplementedError

    @abstractmethod
    def format_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """Shape the raw result into the schema the supervisor/API expects."""
        raise NotImplementedError

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Template method: invoke -> format_output, with logging + error handling.

        Concrete agents should generally be called through `run()` rather
        than `invoke()` directly, so logging and error handling stay
        consistent across all four agents.
        """
        self.logger.info("%s starting (input keys=%s)", self.name, list(input_data.keys()))
        try:
            result = self.invoke(input_data)
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001 - convert unexpected errors into AgentError
            self.logger.error("%s failed unexpectedly: %s", self.name, exc, exc_info=exc)
            raise AgentError(f"{self.name} failed: {exc}") from exc

        output = self.format_output(result)
        self.logger.info("%s finished", self.name)
        return output

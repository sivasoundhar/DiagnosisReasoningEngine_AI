"""Shared pytest fixtures.

Forces an in-memory SQLite DB for the whole test session (set before any
app import) so tests never touch the real data/database.db file.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
# Force-cleared (not setdefault) so a real key sitting in a local .env can never make the
# suite hit the live Groq API - the AI Reasoning Agent's own tests inject a fake LLM
# directly, and supervisor/API tests inject a fake ai_reasoner. Hermetic either way.
os.environ["GROQ_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from src.knowledge.medical_kb import KnowledgeBase
from src.main import app


@pytest.fixture
def client():
    """FastAPI test client, one per test.

    Used as a context manager so FastAPI's lifespan actually runs (startup
    builds app.state.supervisor) - a bare `TestClient(app)` never fires
    startup/shutdown, which only bit us once /analyze started depending on it.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def knowledge_base() -> KnowledgeBase:
    """Shared read-only KB instance - loading JSON is cheap but no need to repeat it per test."""
    return KnowledgeBase()


@pytest.fixture
def sample_patient() -> dict:
    """A representative PatientInput payload for agent/endpoint tests."""
    return {
        "symptoms": ["fever", "cough", "shortness of breath"],
        "labs": {"WBC": 11.2, "CRP": 8.5},
        "age": 45,
        "comorbidities": ["diabetes"],
    }

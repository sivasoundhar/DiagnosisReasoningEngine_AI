"""Tests for the FastAPI endpoints (/analyze, /history/{id}, /feedback)."""
from fastapi.testclient import TestClient


def test_analyze_valid_data_returns_200_with_correct_structure(client: TestClient, sample_patient: dict) -> None:
    response = client.post("/analyze", json=sample_patient)
    assert response.status_code == 200

    body = response.json()
    assert "patient_id" in body and body["patient_id"]
    assert len(body["diagnoses"]) > 0
    assert body["diagnoses"][0]["name"] == "Pneumonia"
    assert "confidence" in body["diagnoses"][0]
    assert "reasoning" in body["diagnoses"][0]
    assert len(body["lab_interpretations"]) == 2
    assert body["risk_assessment"]["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert len(body["recommendation"]["tests"]) > 0
    assert "analyzed_at" in body


def test_analyze_missing_symptoms_returns_400(client: TestClient) -> None:
    response = client.post("/analyze", json={"symptoms": [], "age": 45})
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_analyze_invalid_age_returns_400(client: TestClient) -> None:
    response = client.post("/analyze", json={"symptoms": ["fever"], "age": 500})
    assert response.status_code == 400


def test_analyze_missing_required_fields_returns_400(client: TestClient) -> None:
    response = client.post("/analyze", json={"symptoms": ["fever"]})  # age is required
    assert response.status_code == 400


def test_analyze_generates_patient_id_when_not_provided(client: TestClient, sample_patient: dict) -> None:
    response = client.post("/analyze", json=sample_patient)
    patient_id = response.json()["patient_id"]
    assert len(patient_id) > 0
    # A second call without patient_id gets a different generated id.
    other = client.post("/analyze", json=sample_patient)
    assert other.json()["patient_id"] != patient_id


def test_generated_patient_id_looks_like_an_mrn_not_a_raw_uuid(client: TestClient, sample_patient: dict) -> None:
    """PT-YYYYMMDD-XXXXXX, not a bare UUID4 - reads like a real hospital record number."""
    import re

    response = client.post("/analyze", json=sample_patient)
    patient_id = response.json()["patient_id"]
    assert re.fullmatch(r"PT-\d{8}-[0-9A-F]{6}", patient_id), patient_id


def test_analyze_echoes_provided_patient_id(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "p-123"}
    response = client.post("/analyze", json=payload)
    assert response.json()["patient_id"] == "p-123"


def test_history_valid_patient_returns_200_with_list(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "hist-1"}
    client.post("/analyze", json=payload)

    response = client.get("/history/hist-1")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["patient_id"] == "hist-1"
    assert body[0]["symptoms"] == payload["symptoms"]
    assert body[0]["result"]["diagnoses"][0]["name"] == "Pneumonia"


def test_history_unknown_patient_returns_404(client: TestClient) -> None:
    response = client.get("/history/no-such-patient")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_history_ordered_most_recent_first(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "hist-order"}
    client.post("/analyze", json=payload)
    client.post("/analyze", json={**payload, "symptoms": ["fever"]})

    response = client.get("/history/hist-order")
    body = response.json()
    assert len(body) == 2
    assert body[0]["symptoms"] == ["fever"]  # the second (most recent) call


def test_feedback_valid_patient_returns_200_success(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "fb-1"}
    client.post("/analyze", json=payload)

    response = client.post(
        "/feedback",
        json={"patient_id": "fb-1", "actual_diagnosis": "Pneumonia", "feedback_text": "Confirmed on X-ray."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_feedback_unknown_patient_returns_404(client: TestClient) -> None:
    response = client.post("/feedback", json={"patient_id": "no-such-patient", "actual_diagnosis": "Pneumonia"})
    assert response.status_code == 404


def test_analyze_missing_labs_still_returns_200(client: TestClient) -> None:
    response = client.post("/analyze", json={"symptoms": ["fever", "cough"], "age": 40})
    assert response.status_code == 200
    assert response.json()["lab_interpretations"] == []


def test_analytics_returns_200_with_expected_shape(client: TestClient) -> None:
    """Should never error even with an empty/near-empty table - shape matters more than exact counts,
    since the in-memory DB is shared across tests in this session (see other tests' unique patient_ids)."""
    response = client.get("/analytics")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "total_analyses",
        "unique_patients",
        "risk_level_distribution",
        "top_diagnoses",
        "records_with_feedback",
        "feedback_coverage_pct",
    ):
        assert key in body


def test_analytics_reflects_a_new_analysis(client: TestClient, sample_patient: dict) -> None:
    before = client.get("/analytics").json()["total_analyses"]

    payload = {**sample_patient, "patient_id": "analytics-1"}
    client.post("/analyze", json=payload)

    after = client.get("/analytics").json()
    assert after["total_analyses"] == before + 1
    assert sum(after["risk_level_distribution"].values()) >= 1
    top_names = [d["name"] for d in after["top_diagnoses"]]
    assert "Pneumonia" in top_names


def test_analyze_echoes_patient_name(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "name-1", "patient_name": "Jane Doe"}
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["patient_name"] == "Jane Doe"


def test_analyze_without_patient_name_returns_null(client: TestClient, sample_patient: dict) -> None:
    response = client.post("/analyze", json=sample_patient)
    assert response.json()["patient_name"] is None


def test_history_includes_patient_name_age_and_comorbidities(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "name-hist", "patient_name": "John Smith", "age": 52}
    client.post("/analyze", json=payload)

    response = client.get("/history/name-hist")
    entry = response.json()[0]
    assert entry["patient_name"] == "John Smith"
    assert entry["age"] == 52
    assert entry["comorbidities"] == sample_patient["comorbidities"]


def test_analytics_feedback_coverage_reflects_submitted_feedback(client: TestClient, sample_patient: dict) -> None:
    payload = {**sample_patient, "patient_id": "analytics-fb"}
    client.post("/analyze", json=payload)
    before = client.get("/analytics").json()["records_with_feedback"]

    client.post("/feedback", json={"patient_id": "analytics-fb", "actual_diagnosis": "Pneumonia"})

    after = client.get("/analytics").json()
    assert after["records_with_feedback"] == before + 1
    assert after["feedback_coverage_pct"] > 0

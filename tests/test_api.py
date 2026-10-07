import time
from unittest.mock import patch


def _wait_for_job(client, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"completed", "completed_with_errors", "failed"}:
            return data
        time.sleep(0.05)
    raise AssertionError("Job did not finish in time")


def test_create_generation_job(client):
    payload = {
        "course_name": "Python Workshop",
        "event_date": "2026-03-01",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Jones"},
        ],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "pending"
    assert body["status_url"] == f"/api/jobs/{body['job_id']}"


def test_input_validation_rejects_empty_recipients(client):
    payload = {
        "course_name": "Python Workshop",
        "event_date": "2026-03-01",
        "recipients": [],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_rejects_blank_name(client):
    payload = {
        "course_name": "Python Workshop",
        "event_date": "2026-03-01",
        "recipients": [{"name": "   "}],
    }
    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 422


def test_certificate_generation_and_retrieval(client):
    payload = {
        "course_name": "Data Science Bootcamp",
        "event_date": "2026-04-15",
        "recipients": [{"name": "Carol Lee", "email": "carol@example.com"}],
    }
    create_response = client.post("/api/jobs", json=payload)
    job_id = create_response.json()["job_id"]

    job = _wait_for_job(client, job_id)
    assert job["status"] == "completed"
    assert job["success_count"] == 1
    assert job["failed_count"] == 0

    certificate = job["certificates"][0]
    assert certificate["status"] == "success"
    assert certificate["download_url"] is not None

    download = client.get(certificate["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")


def test_job_status_progress(client):
    payload = {
        "course_name": "Cloud Basics",
        "event_date": "2026-05-01",
        "recipients": [
            {"name": "Dan"},
            {"name": "Eve"},
            {"name": "Frank"},
        ],
    }
    job_id = client.post("/api/jobs", json=payload).json()["job_id"]
    job = _wait_for_job(client, job_id)
    assert job["total_count"] == 3
    assert job["progress_percent"] == 100.0
    assert job["pending_count"] == 0


def test_individual_certificate_failure_does_not_block_others(client):
    payload = {
        "course_name": "Security Training",
        "event_date": "2026-06-01",
        "recipients": [
            {"name": "Grace"},
            {"name": "FAIL GENERATION"},
            {"name": "Henry"},
        ],
    }
    job_id = client.post("/api/jobs", json=payload).json()["job_id"]
    job = _wait_for_job(client, job_id)

    assert job["status"] == "completed_with_errors"
    assert job["success_count"] == 2
    assert job["failed_count"] == 1

    by_name = {c["recipient_name"]: c for c in job["certificates"]}
    assert by_name["Grace"]["status"] == "success"
    assert by_name["Henry"]["status"] == "success"
    assert by_name["FAIL GENERATION"]["status"] == "failed"
    assert by_name["FAIL GENERATION"]["error_message"]


def test_unexpected_generation_error_isolated(client):
    from app.services import generate_certificate_pdf as original_generate

    def flaky_generate(*, output_path, recipient_name, course_name, event_date, force_failure=False):
        if recipient_name == "Ivy":
            raise RuntimeError("disk full")
        return original_generate(
            output_path=output_path,
            recipient_name=recipient_name,
            course_name=course_name,
            event_date=event_date,
            force_failure=force_failure,
        )

    payload = {
        "course_name": "DevOps",
        "event_date": "2026-07-01",
        "recipients": [{"name": "Ivy"}, {"name": "Jack"}],
    }
    with patch("app.services.generate_certificate_pdf", side_effect=flaky_generate):
        job_id = client.post("/api/jobs", json=payload).json()["job_id"]
        job = _wait_for_job(client, job_id)

    assert job["success_count"] == 1
    assert job["failed_count"] == 1
    by_name = {c["recipient_name"]: c for c in job["certificates"]}
    assert "Unexpected error" in by_name["Ivy"]["error_message"]
    assert by_name["Jack"]["status"] == "success"

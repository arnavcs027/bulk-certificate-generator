# Bulk Certificate Generator

Backend API for submitting bulk certificate generation jobs, tracking progress, and downloading generated PDF certificates.

## Tech stack

- **Python 3.11+**
- **FastAPI** for the HTTP API
- **SQLAlchemy** with **SQLite** (relational database; swap `CERT_DATABASE_URL` for PostgreSQL in production)
- **ReportLab** for PDF certificate rendering

## Setup

```bash
cd assignment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Optional environment variables (prefix `CERT_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CERT_DATABASE_URL` | `sqlite:///./certificates.db` | SQLAlchemy database URL |
| `CERT_STORAGE_DIR` | `storage/certificates` | Directory for generated PDF files |

## Run the application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Run tests

```bash
pytest -v
```

Tests use an in-memory SQLite database and a temporary storage directory.

## Submit a certificate generation request

`POST /api/jobs` accepts one job with many recipients (bulk request).

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"course_name\": \"Advanced Python\",
    \"event_date\": \"2026-03-15\",
    \"recipients\": [
      {\"name\": \"Jane Doe\", \"email\": \"jane@example.com\"},
      {\"name\": \"John Smith\", \"email\": \"john@example.com\"}
    ]
  }"
```

Example response (`202 Accepted`):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Certificate generation job accepted and queued for processing.",
  "status_url": "/api/jobs/550e8400-e29b-41d4-a716-446655440000"
}
```

### Validation

- `course_name` and `event_date` are required non-blank strings.
- `recipients` must contain at least one entry (max 5000).
- Each recipient requires a non-blank `name`; `email` is optional but must be valid when provided.

## Check job status / progress

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

The response includes aggregate counts (`success_count`, `failed_count`, `pending_count`), `progress_percent`, job `status`, and per-recipient certificate rows when `include_certificates=true` (default).

Job statuses:

- `pending` — accepted, not yet processing
- `processing` — generation in progress
- `completed` — all certificates succeeded
- `completed_with_errors` — mix of success and failure
- `failed` — every certificate failed

List certificates only:

```bash
curl http://localhost:8000/api/jobs/{job_id}/certificates
```

## Retrieve generated certificates

Each successful certificate exposes `download_url` in the job status payload:

```bash
curl -OJ http://localhost:8000/api/certificates/{certificate_id}/download
```

Downloads return `application/pdf`.

## Design decisions

### Bulk-first API

Clients send **one request** with many recipients. The server creates a **generation job** and one **certificate row** per recipient, so progress and failures are tracked per person without N separate API calls.

### Background processing

Generation runs via FastAPI **BackgroundTasks** after the job is persisted. The HTTP handler returns `202 Accepted` quickly while PDFs are built sequentially in a background worker thread.

**Why not synchronous?** Large recipient lists would block the client and risk timeouts. Background processing keeps the API responsive while still using a simple deployment (no Redis/Celery required for this assignment).

**Trade-off:** BackgroundTasks run in-process. For very large scale or crash recovery, a dedicated queue (Celery, RQ, etc.) and object storage would be the next step.

### Per-recipient failure isolation

Each certificate is generated in its own try/except block. One failure updates that row to `failed` with an `error_message` and continues with remaining recipients. Job status reflects partial success via `completed_with_errors`.

For testing/demos, a recipient named `FAIL GENERATION` intentionally fails generation.

### Storage and template

- A single predefined PDF layout lives in `app/certificate_generator.py` (title, recipient name, course name, date).
- Files are stored on disk under `storage/certificates/{job_id}/{certificate_id}.pdf`; the database stores metadata and paths.

### Database schema

- **`generation_jobs`** — job-level course/event info and aggregate counters.
- **`certificates`** — recipient fields, status, optional error, file path.

This separates job tracking from individual deliverables and supports status queries without scanning the filesystem.

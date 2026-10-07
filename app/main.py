from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Certificate, CertificateStatus, GenerationJob
from app.schemas import CreateJobRequest, CreateJobResponse, JobStatusResponse
from app.services import create_generation_job, job_to_status_response, process_generation_job


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Bulk Certificate Generator",
    description="API for bulk certificate generation with job tracking",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=CreateJobResponse, status_code=202)
def submit_generation_job(
    payload: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CreateJobResponse:
    job = create_generation_job(db, payload)
    background_tasks.add_task(process_generation_job, job.id)
    return CreateJobResponse(
        job_id=job.id,
        status="pending",
        message="Certificate generation job accepted and queued for processing.",
        status_url=f"/api/jobs/{job.id}",
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    include_certificates: bool = True,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_status_response(job, include_certificates=include_certificates)


@app.get("/api/jobs/{job_id}/certificates", response_model=list)
def list_job_certificates(job_id: str, db: Session = Depends(get_db)):
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_status_response(job, include_certificates=True)
    return response.certificates or []


@app.get("/api/certificates/{certificate_id}/download")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.status != CertificateStatus.SUCCESS or not certificate.file_path:
        raise HTTPException(
            status_code=404,
            detail="Certificate is not available for download",
        )

    path = Path(certificate.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Certificate file missing on disk")

    filename = f"{certificate.recipient_name.replace(' ', '_')}_certificate.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
    )

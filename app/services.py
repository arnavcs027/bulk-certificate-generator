from sqlalchemy import select
from sqlalchemy.orm import Session

from app.certificate_generator import CertificateGenerationError, generate_certificate_pdf
from app.config import settings
from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.schemas import CreateJobRequest


def create_generation_job(db: Session, payload: CreateJobRequest) -> GenerationJob:
    job = GenerationJob(
        course_name=payload.course_name,
        event_date=payload.event_date,
        status=JobStatus.PENDING,
        total_count=len(payload.recipients),
    )
    db.add(job)
    db.flush()

    for recipient in payload.recipients:
        db.add(
            Certificate(
                job_id=job.id,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email) if recipient.email else None,
                status=CertificateStatus.PENDING,
            )
        )

    db.commit()
    db.refresh(job)
    return job


def _refresh_job_counts(db: Session, job: GenerationJob) -> None:
    certificates = db.scalars(select(Certificate).where(Certificate.job_id == job.id)).all()
    job.success_count = sum(1 for c in certificates if c.status == CertificateStatus.SUCCESS)
    job.failed_count = sum(1 for c in certificates if c.status == CertificateStatus.FAILED)
    pending = sum(1 for c in certificates if c.status == CertificateStatus.PENDING)

    if pending == 0:
        if job.failed_count == 0:
            job.status = JobStatus.COMPLETED
        elif job.success_count == 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.COMPLETED_WITH_ERRORS
    else:
        job.status = JobStatus.PROCESSING


def process_generation_job(job_id: str) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return

        job.status = JobStatus.PROCESSING
        db.commit()

        certificates = db.scalars(
            select(Certificate).where(Certificate.job_id == job_id).order_by(Certificate.created_at)
        ).all()

        for certificate in certificates:
            if certificate.status != CertificateStatus.PENDING:
                continue

            file_path = settings.storage_dir / job_id / f"{certificate.id}.pdf"
            try:
                generate_certificate_pdf(
                    output_path=file_path,
                    recipient_name=certificate.recipient_name,
                    course_name=job.course_name,
                    event_date=job.event_date,
                )
                certificate.status = CertificateStatus.SUCCESS
                certificate.file_path = str(file_path)
                certificate.error_message = None
            except CertificateGenerationError as exc:
                certificate.status = CertificateStatus.FAILED
                certificate.error_message = str(exc)
            except Exception as exc:  # noqa: BLE001 — isolate per-recipient failures
                certificate.status = CertificateStatus.FAILED
                certificate.error_message = f"Unexpected error: {exc}"

            db.commit()
            db.refresh(job)
            _refresh_job_counts(db, job)
            db.commit()

        db.refresh(job)
        _refresh_job_counts(db, job)
        db.commit()
    finally:
        db.close()


def job_to_status_response(job: GenerationJob, include_certificates: bool = False):
    from app.schemas import CertificateSummary, JobStatusResponse

    pending_count = job.total_count - job.success_count - job.failed_count
    progress = 0.0
    if job.total_count:
        progress = round(((job.success_count + job.failed_count) / job.total_count) * 100, 2)

    certificates = None
    if include_certificates:
        certificates = [
            CertificateSummary(
                id=c.id,
                recipient_name=c.recipient_name,
                recipient_email=c.recipient_email,
                status=c.status,
                error_message=c.error_message,
                download_url=f"/api/certificates/{c.id}/download"
                if c.status == CertificateStatus.SUCCESS
                else None,
            )
            for c in job.certificates
        ]

    return JobStatusResponse(
        id=job.id,
        course_name=job.course_name,
        event_date=job.event_date,
        status=job.status,
        total_count=job.total_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        pending_count=pending_count,
        progress_percent=progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        certificates=certificates,
    )

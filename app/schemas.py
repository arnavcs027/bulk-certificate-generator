from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import CertificateStatus, JobStatus


class RecipientInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Recipient name cannot be blank")
        return cleaned


class CreateJobRequest(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=255)
    event_date: str = Field(..., min_length=1, max_length=64)
    recipients: list[RecipientInput] = Field(..., min_length=1, max_length=5000)

    @field_validator("course_name", "event_date")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank")
        return cleaned


class CertificateSummary(BaseModel):
    id: str
    recipient_name: str
    recipient_email: str | None
    status: CertificateStatus
    error_message: str | None
    download_url: str | None

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: str
    course_name: str
    event_date: str
    status: JobStatus
    total_count: int
    success_count: int
    failed_count: int
    pending_count: int
    progress_percent: float
    created_at: datetime
    updated_at: datetime
    certificates: list[CertificateSummary] | None = None

    model_config = {"from_attributes": True}


class CreateJobResponse(BaseModel):
    job_id: str
    status: Literal["pending"]
    message: str
    status_url: str

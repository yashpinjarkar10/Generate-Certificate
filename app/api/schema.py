from datetime import date as dt_date
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


# 1. POST /generate-certificate

class CertificateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Recipient's name (Compulsory)")
    course: str = Field(
        default="Python",
        description="Course name (Optional, defaults to Python)",
    )
    date: dt_date = Field(
        default_factory=dt_date.today,
        description="Completion date (Optional, defaults to today's date)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Recipient name is compulsory and cannot be blank")
        return v.strip()

    @field_validator("course", mode="before")
    @classmethod
    def set_course_default(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Python"
        return str(v).strip()

    @field_validator("date", mode="before")
    @classmethod
    def set_date_default(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return dt_date.today()
        return v


class GenerateCertificateRequest(BaseModel):
    certificates: list[CertificateRequest] = Field(
        ...,
        min_length=1,
        description="List of certificate requests to process in bulk",
    )


class GenerateCertificateResponse(BaseModel):
    job_id: str
    status: str
    total: int


# 2. GET /{job_id}

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    completed: int
    failed: int


# 3. GET /{job_id}/certificates

class CertificateResponse(BaseModel):
    certificate_id: str
    name: str
    status: str
    url: Optional[str] = None


class CertificatesResponse(BaseModel):
    job_id: str
    status: str
    total: int
    completed: int
    failed: int
    certificates: list[CertificateResponse]


# 4. GET /{job_id}/certificates/{certificate_id}
# Response: CertificateResponse


# 5. DELETE /{job_id}

class CancelJobResponse(BaseModel):
    job_id: str
    status: str
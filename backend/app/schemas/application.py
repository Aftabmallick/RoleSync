import uuid
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    company_name: str = Field(..., description="Target company name")
    job_title: str = Field(..., description="Target job title")
    job_url: Optional[str] = Field("", description="Job posting or application URL")
    ats_provider: Optional[str] = Field("GENERIC", description="ATS provider (Greenhouse, Lever, Workday, etc.)")
    ats_score: Optional[float] = Field(0.0, description="ATS match score percentage")
    status: Optional[str] = Field("APPLIED", description="Application status (DRAFT, APPLIED, INTERVIEWING, OFFERED, REJECTED)")
    notes: Optional[str] = Field("", description="Candidate notes or interview logs")
    tailored_summary: Optional[str] = Field("", description="Summary or snippet tailored for this role")


class ApplicationUpdate(BaseModel):
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[str] = None
    ats_score: Optional[float] = None
    notes: Optional[str] = None
    job_url: Optional[str] = None


class ApplicationItem(BaseModel):
    id: str
    user_id: str
    company_name: str
    job_title: str
    job_url: Optional[str] = ""
    ats_provider: Optional[str] = "GENERIC"
    ats_score: float = 0.0
    status: str = "APPLIED"
    notes: Optional[str] = ""
    tailored_summary: Optional[str] = ""
    applied_at: str
    created_at: str
    updated_at: str


class ApplicationListResponse(BaseModel):
    total: int
    applications: List[ApplicationItem]

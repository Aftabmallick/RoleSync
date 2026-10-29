from typing import List, Optional
from pydantic import BaseModel, Field


class RecruiterSearchRequest(BaseModel):
    company_name: str = Field(..., description="Target company name")
    domain: Optional[str] = Field(None, description="Company website domain if known")
    role_title: Optional[str] = Field(None, description="Target job title to match relevant recruiter or hiring manager")
    department: Optional[str] = Field("Engineering", description="Target department")


class RecruiterContact(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    email: str
    title: str
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    verification_status: str  # 'valid', 'risky', 'invalid'
    linkedin_url: Optional[str] = None


class RecruiterSearchResponse(BaseModel):
    company_name: str
    domain: str
    recruiters: List[RecruiterContact]


class DeliverabilityCheckRequest(BaseModel):
    email: str = Field(..., description="Email address to verify")


class DeliverabilityResult(BaseModel):
    email: str
    status: str  # 'valid', 'risky', 'invalid'
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    is_deliverable: bool
    smtp_check_performed: bool = Field(False, description="Must be False - raw port 25 SMTP checks are prohibited")
    provider: str = "Hunter/ZeroBounce REST"


class OutreachSynthesizeRequest(BaseModel):
    candidate_name: str
    candidate_role: str
    candidate_summary: str
    recruiter_name: str
    recruiter_email: str
    recruiter_title: str
    company_name: str
    target_job_title: str
    physical_address: Optional[str] = "RoleSync Technologies Inc., 100 Montgomery St, Suite 1400, San Francisco, CA 94104"
    mode: str = Field("copilot", description="'copilot' (manual review) or 'autopilot' (staggered queue)")


class OutreachDraft(BaseModel):
    subject: str
    body_text: str
    word_count: int
    recipient_email: str
    opt_out_link: str
    physical_address: str
    is_compliant: bool
    validation_errors: List[str] = []


class OutreachSynthesizeResponse(BaseModel):
    draft: OutreachDraft
    mode: str
    status: str  # 'READY_FOR_PREVIEW' or 'ENQUEUED_AUTOPILOT'
    daily_quota_remaining: int

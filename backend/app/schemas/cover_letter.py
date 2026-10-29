from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CoverLetterRequest(BaseModel):
    target_role: str = Field(..., description="Target role name (e.g. Senior Backend Engineer)")
    company_name: str = Field(..., description="Target company name (e.g. Stripe)")
    raw_job_description: str = Field(..., description="Full text of the job posting")
    candidate_name: Optional[str] = Field("Alex Mercer", description="Candidate full name")
    candidate_summary: Optional[str] = Field("", description="Candidate summary or bio")
    master_profile: Optional[Dict[str, Any]] = Field(None, description="Full Master Profile data")
    tone: Optional[str] = Field("professional", description="Tone: professional, confident, enthusiastic")


class CoverLetterResponse(BaseModel):
    company_name: str
    target_role: str
    candidate_name: str
    subject: str
    salutation: str
    opening_paragraph: str
    body_paragraphs: List[str]
    closing_paragraph: str
    full_text: str
    word_count: int
    matched_skills: List[str]

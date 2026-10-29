from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TailorRequest(BaseModel):
    job_id: Optional[str] = None
    target_role: str
    company_name: str
    raw_job_description: str
    custom_instructions: Optional[str] = None
    required_years: Optional[float] = 3.0


class TailorTaskResponse(BaseModel):
    task_id: str
    status: str = "QUEUED"  # QUEUED, PROCESSING, COMPLETED, FAILED
    message: str = "Resume tailoring task has been successfully enqueued."


class TailorResultResponse(BaseModel):
    task_id: str
    status: str
    ats_score: Optional[Dict[str, Any]] = None
    tailored_draft: Optional[Dict[str, Any]] = None
    pdf_base64: Optional[str] = None
    error: Optional[str] = None

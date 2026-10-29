from fastapi import APIRouter, Depends, status
from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse
from app.services.cover_letter_service import CoverLetterService
from app.core.jwt import get_current_user_id

router = APIRouter(prefix="/cover-letter", tags=["Cover Letter Generator"])


@router.post("/synthesize", response_model=CoverLetterResponse, status_code=status.HTTP_200_OK)
async def synthesize_cover_letter(
    payload: CoverLetterRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Synthesizes a customized, ATS-aligned, zero-hallucination cover letter
    tailored to the target role and company using candidate Master Profile accomplishments.
    """
    return CoverLetterService.generate_cover_letter(
        target_role=payload.target_role,
        company_name=payload.company_name,
        raw_job_description=payload.raw_job_description,
        candidate_name=payload.candidate_name or "Alex Mercer",
        candidate_summary=payload.candidate_summary,
        master_profile=payload.master_profile,
        tone=payload.tone or "professional"
    )

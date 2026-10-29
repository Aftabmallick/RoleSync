from fastapi import APIRouter, Depends, HTTPException, status
from app.core.jwt import get_current_user_id
from app.schemas.resume_enhancer import (
    ResumeMatchRequest,
    ResumeMatchResponse,
    ApplyEnhancementsRequest,
    ResumeVersionItem,
    ResumeVersionListResponse
)
from app.services.resume_enhancer_service import ResumeEnhancerService

router = APIRouter(prefix="/resume", tags=["Resume Match & Enhancer"])


@router.post("/match-and-suggest", response_model=ResumeMatchResponse, status_code=status.HTTP_200_OK)
async def match_resume_and_suggest_additions(
    payload: ResumeMatchRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Benchmarks selected resume (base or version) against target JD.
    Returns current ATS score, potential score, and suggested additions (skills, bullets, summary).
    """
    return ResumeEnhancerService.match_and_suggest(
        job_description=payload.job_description,
        target_role=payload.target_role,
        company_name=payload.company_name,
        resume=payload.resume
    )


@router.post("/apply-enhancements", response_model=ResumeVersionItem, status_code=status.HTTP_201_CREATED)
async def apply_enhancements_and_save_version(
    payload: ApplyEnhancementsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Applies candidate-accepted additions to the resume, compiles single-page PDF
    strictly preserving the base resume structure, and persists as a new resume version.
    """
    bullet_updates = [item.model_dump() for item in payload.accepted_bullet_updates]
    return ResumeEnhancerService.apply_enhancements_and_save(
        base_resume=payload.base_resume,
        target_role=payload.target_role,
        company_name=payload.company_name,
        version_name=payload.version_name,
        accepted_skills=payload.accepted_skills,
        accepted_summary=payload.accepted_summary,
        accepted_bullet_updates=bullet_updates,
        user_id=user_id
    )


@router.get("/versions", response_model=ResumeVersionListResponse)
async def get_resume_versions(user_id: str = Depends(get_current_user_id)):
    """
    Retrieves all enhanced resume versions for the candidate.
    """
    versions = ResumeEnhancerService.list_versions(user_id)
    return ResumeVersionListResponse(total=len(versions), versions=versions)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume_version(
    version_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Deletes a saved resume version.
    """
    deleted = ResumeEnhancerService.delete_version(user_id, version_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found.")
    return None


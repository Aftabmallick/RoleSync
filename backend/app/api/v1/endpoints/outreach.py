from fastapi import APIRouter, HTTPException, Depends
from app.schemas.outreach import (
    RecruiterSearchRequest,
    RecruiterSearchResponse,
    DeliverabilityCheckRequest,
    DeliverabilityResult,
    OutreachSynthesizeRequest,
    OutreachSynthesizeResponse,
)
from app.services.outreach_service import OutreachService, OutreachComplianceError
from app.core.jwt import get_current_user_id

router = APIRouter(prefix="/outreach", tags=["Outreach & Recruiter Discovery"])


@router.post("/discover", response_model=RecruiterSearchResponse)
async def discover_recruiters(
    payload: RecruiterSearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Identifies hiring managers and technical recruiters for a target company via Hunter.io / Apollo REST schema.
    """
    domain, recruiters = OutreachService.discover_recruiters(
        company_name=payload.company_name,
        domain=payload.domain,
        role_title=payload.role_title,
        department=payload.department or "Engineering",
    )
    return RecruiterSearchResponse(
        company_name=payload.company_name,
        domain=domain,
        recruiters=recruiters,
    )


@router.post("/verify", response_model=DeliverabilityResult)
async def verify_recruiter_email(
    payload: DeliverabilityCheckRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Validates deliverability via ZeroBounce / Hunter API without raw port 25 SMTP handshakes.
    """
    result = OutreachService.verify_email_deliverability(payload.email)
    return result


@router.post("/synthesize", response_model=OutreachSynthesizeResponse)
async def synthesize_outreach_email(
    payload: OutreachSynthesizeRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Generates a CAN-SPAM and GDPR Article 6 compliant cold outreach draft (< 120 words, opt-out link, physical address).
    Enforces candidate daily quota in Autopilot mode (max 15/day).
    """
    try:
        response = OutreachService.synthesize_outreach_email(
            candidate_name=payload.candidate_name,
            candidate_role=payload.candidate_role,
            candidate_summary=payload.candidate_summary,
            recruiter_name=payload.recruiter_name,
            recruiter_email=payload.recruiter_email,
            recruiter_title=payload.recruiter_title,
            company_name=payload.company_name,
            target_job_title=payload.target_job_title,
            physical_address=payload.physical_address,
            mode=payload.mode,
            user_id=user_id,
        )
        return response
    except OutreachComplianceError as e:
        raise HTTPException(status_code=400, detail=str(e))


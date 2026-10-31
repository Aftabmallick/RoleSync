import json
import logging
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.jwt import get_optional_user_id
from app.core.security import EnvelopeEncryption
from app.models.profile import MasterProfile
from app.api.v1.endpoints.profile import encrypted_profiles_db, to_uuid
from app.schemas.tailor import TailorRequest, TailorTaskResponse, TailorResultResponse
from app.tasks.tailor_tasks import orchestrator, task_store
from app.core.limiter import limiter

logger = logging.getLogger("rolesync.tailor")

router = APIRouter(prefix="/tailor", tags=["Resume Tailoring"])


def extract_candidate_name(profile: Dict[str, Any]) -> str:
    """Extract candidate full name from various possible profile structures."""
    if not isinstance(profile, dict):
        return ""
    personal = profile.get("personal") or profile.get("personal_info")
    if isinstance(personal, dict):
        name = personal.get("full_name") or personal.get("name") or ""
        if name and str(name).strip():
            return str(name).strip()
    name = profile.get("full_name") or profile.get("name") or ""
    return str(name).strip()


def is_complete_profile(profile: Optional[Dict[str, Any]]) -> bool:
    """Validates that candidate master profile has full_name, skills, and experience."""
    if not profile or not isinstance(profile, dict):
        return False
    name = extract_candidate_name(profile)
    if not name:
        return False
    skills = profile.get("skills")
    if not skills or not isinstance(skills, list) or len(skills) == 0:
        return False
    experience = profile.get("experience")
    if not experience or not isinstance(experience, list) or len(experience) == 0:
        return False
    return True


@router.post("", response_model=TailorTaskResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("20/minute")
async def enqueue_tailoring_task(
    request: Request,
    payload: TailorRequest,
    background_tasks: BackgroundTasks,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Enqueues an asynchronous resume tailoring task.
    Returns 202 Accepted with a task_id to prevent HTTP gateway timeouts.
    """
    effective_profile = dict(payload.master_profile) if payload.master_profile else None

    # If payload.master_profile is missing or incomplete, attempt to load from database for authenticated user
    if not is_complete_profile(effective_profile):
        db_profile = None
        if user_id:
            try:
                u_id = to_uuid(user_id)
                stmt = select(MasterProfile).where(MasterProfile.user_id == u_id, MasterProfile.is_current == True)
                res = await db.execute(stmt)
                record = res.scalars().first()
                if record and record.encrypted_profile_data and record.encryption_iv:
                    decrypted_bytes = EnvelopeEncryption.decrypt(
                        ciphertext=record.encrypted_profile_data,
                        iv=record.encryption_iv,
                        user_id=str(user_id)
                    )
                    db_profile = json.loads(decrypted_bytes.decode("utf-8"))
            except Exception as e:
                logger.warning(f"Failed to query database profile for user {user_id}: {e}")
                db_profile = None

            if not db_profile and user_id in encrypted_profiles_db:
                in_memory = encrypted_profiles_db.get(user_id)
                if in_memory and "ciphertext" in in_memory and "iv" in in_memory:
                    try:
                        decrypted_bytes = EnvelopeEncryption.decrypt(
                            ciphertext=in_memory["ciphertext"],
                            iv=in_memory["iv"],
                            user_id=str(user_id)
                        )
                        db_profile = json.loads(decrypted_bytes.decode("utf-8"))
                    except Exception as e:
                        logger.warning(f"Failed to decrypt in-memory profile for user {user_id}: {e}")
                        db_profile = None

        if is_complete_profile(db_profile):
            effective_profile = db_profile
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Master profile with candidate identity is required for tailoring"
            )

    # Ensure experience bullet IDs are assigned
    for i, exp in enumerate(effective_profile.get("experience", [])):
        if not exp.get("bullets"):
            exp["bullets"] = [
                {
                    "id": f"b_{i+1}_1",
                    "text": f"Engineered scalable infrastructure and microservices at {exp.get('company', 'Tech Organization')}."
                }
            ]
        else:
            for j, b in enumerate(exp["bullets"]):
                if isinstance(b, dict) and not b.get("id"):
                    b["id"] = f"b_{i+1}_{j+1}"

    task_id = f"task_{uuid.uuid4().hex}"
    task_store[task_id] = {"status": "QUEUED", "stage": "INITIALIZED"}
    task_user_id = user_id or "usr_candidate"

    # Dispatch via Celery if worker/broker is available, otherwise fallback to in-process background_tasks
    dispatched_to_celery = False
    try:
        from app.tasks.tailor_tasks import run_tailoring_pipeline_task
        # Try pinging broker with short timeout
        with run_tailoring_pipeline_task.app.connection_for_write() as conn:
            conn.connect()
            run_tailoring_pipeline_task.apply_async(
                kwargs={
                    "task_id": task_id,
                    "user_id": task_user_id,
                    "master_profile": effective_profile,
                    "raw_jd": payload.raw_job_description,
                    "target_role": payload.target_role,
                    "company_name": payload.company_name,
                    "required_years": payload.required_years or 3.0
                }
            )
            dispatched_to_celery = True
    except Exception:
        dispatched_to_celery = False

    if not dispatched_to_celery:
        background_tasks.add_task(
            orchestrator.execute_tailoring_pipeline,
            task_id=task_id,
            user_id=task_user_id,
            master_profile=effective_profile,
            raw_jd=payload.raw_job_description,
            target_role=payload.target_role,
            company_name=payload.company_name,
            required_years=payload.required_years or 3.0
        )

    return TailorTaskResponse(
        task_id=task_id,
        status="QUEUED",
        message="Resume tailoring task enqueued successfully."
    )


@router.get("/{task_id}", response_model=TailorResultResponse)
async def get_tailoring_task_status(task_id: str):
    """Queries current status, ATS score, and generated Typst PDF of a tailoring task."""
    record = task_store.get(task_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )

    return TailorResultResponse(
        task_id=task_id,
        status=record.get("status", "UNKNOWN"),
        ats_score=record.get("ats_score"),
        tailored_draft=record.get("tailored_draft"),
        pdf_base64=record.get("pdf_base64"),
        error=record.get("error")
    )

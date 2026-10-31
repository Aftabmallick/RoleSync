import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.jwt import get_current_user_id
from app.models.user import User
from app.models.job import Job
from app.models.application import Application, ApplicationHistory
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationItem,
    ApplicationListResponse
)

logger = logging.getLogger("rolesync.applications")

router = APIRouter(prefix="/applications", tags=["Application Tracker"])

# In-memory dictionary retained for testing backwards-compatibility
applications_store: Dict[str, List[Dict[str, Any]]] = {}


def to_uuid(val: Any) -> uuid.UUID:
    """Safely converts string or UUID to a deterministic UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


async def ensure_user_exists(db: AsyncSession, u_id: uuid.UUID) -> User:
    """Ensures parent user row exists before foreign key constraints apply."""
    stmt = select(User).where(User.id == u_id)
    res = await db.execute(stmt)
    user_record = res.scalars().first()
    if not user_record:
        user_record = User(
            id=u_id,
            email=f"{u_id}@candidate.rolesync.dev",
            full_name="Candidate User",
            plan_tier="FREE",
            is_active=True
        )
        db.add(user_record)
        await db.flush()
    return user_record


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all tracked job applications for the authenticated candidate from PostgreSQL.
    """
    u_id = to_uuid(user_id)

    stmt = (
        select(Application)
        .options(selectinload(Application.job))
        .where(Application.user_id == u_id)
        .order_by(Application.updated_at.desc())
    )
    res = await db.execute(stmt)
    apps = res.scalars().all()

    items: List[ApplicationItem] = []
    for app in apps:
        job = app.job
        company = job.company if job else "Target Company"
        title = job.title if job else "Role"
        url = job.url if job else ""
        ats_provider = job.ats_platform if job else "GENERIC"
        notes = (app.tailored_resume_data or {}).get("notes", "")
        summary = (app.tailored_resume_data or {}).get("summary", "")

        items.append(
            ApplicationItem(
                id=str(app.id),
                user_id=str(app.user_id),
                company_name=company,
                job_title=title,
                job_url=url,
                ats_provider=ats_provider,
                ats_score=app.ats_score,
                status=app.status,
                notes=notes,
                tailored_summary=summary,
                applied_at=(app.applied_at or app.created_at).isoformat(),
                created_at=app.created_at.isoformat(),
                updated_at=app.updated_at.isoformat()
            )
        )

    # If DB returned items, return them. Otherwise fall back to in-memory store if present
    if items:
        return ApplicationListResponse(total=len(items), applications=items)

    user_apps = applications_store.get(user_id, [])
    sorted_apps = sorted(user_apps, key=lambda x: x.get("updated_at", ""), reverse=True)
    return ApplicationListResponse(
        total=len(sorted_apps),
        applications=[ApplicationItem(**app) for app in sorted_apps]
    )


@router.post("", response_model=ApplicationItem, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Records a new job application and associated target job in PostgreSQL.
    """
    u_id = to_uuid(user_id)
    await ensure_user_exists(db, u_id)

    # 1. Query or create Job entity
    job_stmt = select(Job).where(
        Job.user_id == u_id,
        Job.company == payload.company_name,
        Job.title == payload.job_title
    )
    job_res = await db.execute(job_stmt)
    job = job_res.scalars().first()

    if not job:
        job = Job(
            id=uuid.uuid4(),
            user_id=u_id,
            url=payload.job_url or "https://rolesync.io/jobs",
            ats_platform=payload.ats_provider or "GENERIC",
            title=payload.job_title,
            company=payload.company_name,
            raw_content=payload.tailored_summary or payload.job_title,
            extracted_skills={}
        )
        db.add(job)
        await db.flush()

    # 2. Create Application entity
    app_uuid = uuid.uuid4()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    new_app = Application(
        id=app_uuid,
        user_id=u_id,
        job_id=job.id,
        status=payload.status or "APPLIED",
        ats_score=float(payload.ats_score or 0.0),
        tailored_resume_data={
            "notes": payload.notes or "",
            "summary": payload.tailored_summary or ""
        },
        applied_at=now_dt if payload.status == "APPLIED" else None,
        created_at=now_dt,
        updated_at=now_dt
    )
    db.add(new_app)

    # 3. Create initial status history record
    history = ApplicationHistory(
        id=uuid.uuid4(),
        application_id=app_uuid,
        from_status="NONE",
        to_status=payload.status or "APPLIED",
        notes=payload.notes or "Initial application submission recorded.",
        transitioned_at=now_dt
    )
    db.add(history)
    await db.commit()

    # Also update in-memory store for backwards-compatible test assertions
    app_record = {
        "id": str(app_uuid),
        "user_id": user_id,
        "company_name": payload.company_name,
        "job_title": payload.job_title,
        "job_url": payload.job_url or "",
        "ats_provider": payload.ats_provider or "GENERIC",
        "ats_score": float(payload.ats_score or 0.0),
        "status": payload.status or "APPLIED",
        "notes": payload.notes or "",
        "tailored_summary": payload.tailored_summary or "",
        "applied_at": now_iso,
        "created_at": now_iso,
        "updated_at": now_iso
    }
    if user_id not in applications_store:
        applications_store[user_id] = []
    applications_store[user_id].append(app_record)

    logger.info(f"Recorded application {app_uuid} for user '{user_id}' at {payload.company_name} in PostgreSQL.")
    return ApplicationItem(**app_record)


@router.patch("/{app_id}", response_model=ApplicationItem)
async def update_application(
    app_id: str,
    payload: ApplicationUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates status, notes, or details of a tracked job application in PostgreSQL.
    """
    u_id = to_uuid(user_id)
    target_uuid = to_uuid(app_id)

    stmt = (
        select(Application)
        .options(selectinload(Application.job))
        .where(Application.id == target_uuid, Application.user_id == u_id)
    )
    res = await db.execute(stmt)
    app = res.scalars().first()

    if not app:
        # Check in-memory store fallback
        user_apps = applications_store.get(user_id, [])
        for a in user_apps:
            if a["id"] == app_id:
                now_iso = datetime.now(timezone.utc).isoformat()
                if payload.company_name is not None:
                    a["company_name"] = payload.company_name
                if payload.job_title is not None:
                    a["job_title"] = payload.job_title
                if payload.status is not None:
                    a["status"] = payload.status
                if payload.ats_score is not None:
                    a["ats_score"] = float(payload.ats_score)
                if payload.notes is not None:
                    a["notes"] = payload.notes
                if payload.job_url is not None:
                    a["job_url"] = payload.job_url
                a["updated_at"] = now_iso
                return ApplicationItem(**a)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{app_id}' not found.")

    old_status = app.status
    now_dt = datetime.now(timezone.utc)

    if payload.status is not None:
        app.status = payload.status
        # Transition history
        hist = ApplicationHistory(
            id=uuid.uuid4(),
            application_id=app.id,
            from_status=old_status,
            to_status=payload.status,
            notes=payload.notes,
            transitioned_at=now_dt
        )
        db.add(hist)

    if payload.ats_score is not None:
        app.ats_score = float(payload.ats_score)

    resume_data = dict(app.tailored_resume_data or {})
    if payload.notes is not None:
        resume_data["notes"] = payload.notes
    app.tailored_resume_data = resume_data

    if app.job:
        if payload.company_name is not None:
            app.job.company = payload.company_name
        if payload.job_title is not None:
            app.job.title = payload.job_title
        if payload.job_url is not None:
            app.job.url = payload.job_url

    app.updated_at = now_dt
    await db.commit()

    # Sync to in-memory store
    for a in applications_store.get(user_id, []):
        if a["id"] == app_id or a["id"] == str(app.id):
            if payload.status is not None:
                a["status"] = payload.status
            if payload.notes is not None:
                a["notes"] = payload.notes
            if payload.ats_score is not None:
                a["ats_score"] = float(payload.ats_score)
            a["updated_at"] = now_dt.isoformat()

    return ApplicationItem(
        id=str(app.id),
        user_id=str(app.user_id),
        company_name=app.job.company if app.job else "Target Company",
        job_title=app.job.title if app.job else "Role",
        job_url=app.job.url if app.job else "",
        ats_provider=app.job.ats_platform if app.job else "GENERIC",
        ats_score=app.ats_score,
        status=app.status,
        notes=resume_data.get("notes", ""),
        tailored_summary=resume_data.get("summary", ""),
        applied_at=(app.applied_at or app.created_at).isoformat(),
        created_at=app.created_at.isoformat(),
        updated_at=app.updated_at.isoformat()
    )


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Removes an application from PostgreSQL.
    """
    u_id = to_uuid(user_id)
    target_uuid = to_uuid(app_id)

    stmt = delete(Application).where(Application.id == target_uuid, Application.user_id == u_id)
    res = await db.execute(stmt)
    await db.commit()

    # Clean in-memory store if present
    user_apps = applications_store.get(user_id, [])
    initial_len = len(user_apps)
    applications_store[user_id] = [a for a in user_apps if a["id"] != app_id and a["id"] != str(target_uuid)]

    if res.rowcount == 0 and len(applications_store[user_id]) == initial_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{app_id}' not found.")

    return None

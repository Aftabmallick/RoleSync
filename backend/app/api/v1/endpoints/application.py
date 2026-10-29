import json
import logging
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.jwt import get_current_user_id
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationItem,
    ApplicationListResponse
)

logger = logging.getLogger("rolesync.applications")

router = APIRouter(prefix="/applications", tags=["Application Tracker"])

APP_DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "applications.json"

# user_id -> List[Dict]
applications_store: Dict[str, List[Dict[str, Any]]] = {}


def _load_applications():
    try:
        if APP_DB_PATH.exists():
            with open(APP_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                applications_store.clear()
                applications_store.update(data)
    except Exception as e:
        logger.warning(f"Could not load applications: {e}")


def _save_applications():
    try:
        APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(applications_store, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save applications: {e}")


_load_applications()


@router.get("", response_model=ApplicationListResponse)
async def list_applications(user_id: str = Depends(get_current_user_id)):
    """
    Lists all tracked job applications for the authenticated candidate.
    """
    user_apps = applications_store.get(user_id, [])
    # Sort descending by applied_at / updated_at
    sorted_apps = sorted(user_apps, key=lambda x: x.get("updated_at", ""), reverse=True)
    return ApplicationListResponse(
        total=len(sorted_apps),
        applications=[ApplicationItem(**app) for app in sorted_apps]
    )


@router.post("", response_model=ApplicationItem, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    user_id: str = Depends(get_current_user_id)
):
    """
    Records a new job application in the tracker.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    app_id = f"app_{uuid.uuid4().hex[:12]}"

    app_record = {
        "id": app_id,
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
    _save_applications()

    logger.info(f"Recorded application {app_id} for user '{user_id}' at {payload.company_name}.")
    return ApplicationItem(**app_record)


@router.patch("/{app_id}", response_model=ApplicationItem)
async def update_application(
    app_id: str,
    payload: ApplicationUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """
    Updates status, notes, or details of a tracked job application.
    """
    user_apps = applications_store.get(user_id, [])
    for app in user_apps:
        if app["id"] == app_id:
            now_iso = datetime.now(timezone.utc).isoformat()
            if payload.company_name is not None:
                app["company_name"] = payload.company_name
            if payload.job_title is not None:
                app["job_title"] = payload.job_title
            if payload.status is not None:
                app["status"] = payload.status
            if payload.ats_score is not None:
                app["ats_score"] = float(payload.ats_score)
            if payload.notes is not None:
                app["notes"] = payload.notes
            if payload.job_url is not None:
                app["job_url"] = payload.job_url

            app["updated_at"] = now_iso
            _save_applications()
            return ApplicationItem(**app)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{app_id}' not found.")


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Removes an application from the tracker.
    """
    user_apps = applications_store.get(user_id, [])
    initial_len = len(user_apps)
    applications_store[user_id] = [app for app in user_apps if app["id"] != app_id]

    if len(applications_store[user_id]) == initial_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{app_id}' not found.")

    _save_applications()
    return None

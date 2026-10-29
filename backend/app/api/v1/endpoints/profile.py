import base64
import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form
from app.core.jwt import get_current_user_id
from app.core.security import EnvelopeEncryption
from app.schemas.profile import (
    MasterProfilePayload,
    MasterProfileResponse,
    ResumeParseRequest,
    ResumeParseResponse
)
from app.services.resume_parser import resume_parser

logger = logging.getLogger("rolesync.profile")

router = APIRouter(prefix="/profile", tags=["Master Profile"])

# Encrypted profile store (simulating encrypted column storage in PostgreSQL master_profiles)
# user_id -> {"version": int, "ciphertext": bytes, "iv": bytes, "updated_at": str}
DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "encrypted_profiles.json"
encrypted_profiles_db: Dict[str, Dict[str, Any]] = {}


def _load_persisted_profiles():
    try:
        if DB_PATH.exists():
            with open(DB_PATH, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for uid, rec in raw_data.items():
                    encrypted_profiles_db[uid] = {
                        "version": rec["version"],
                        "ciphertext": base64.b64decode(rec["ciphertext"]),
                        "iv": base64.b64decode(rec["iv"]),
                        "updated_at": rec["updated_at"]
                    }
    except Exception as e:
        logger.warning(f"Could not load persisted profiles: {e}")


def _save_persisted_profiles():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        dump_data = {}
        for uid, rec in encrypted_profiles_db.items():
            dump_data[uid] = {
                "version": rec["version"],
                "ciphertext": base64.b64encode(rec["ciphertext"]).decode("utf-8"),
                "iv": base64.b64encode(rec["iv"]).decode("utf-8"),
                "updated_at": rec["updated_at"]
            }
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not persist encrypted profiles: {e}")


_load_persisted_profiles()

DEFAULT_SAMPLE_PROFILE: Dict[str, Any] = {
    "personal": {
        "full_name": "Alex Mercer",
        "email": "alex@mercer.dev",
        "phone": "+1 555-019-2834",
        "location": "San Francisco, CA",
        "linkedin": "linkedin.com/in/alex-mercer",
        "github": "github.com/alexmercer"
    },
    "skills": [
        {"name": "Python", "category": "Languages"},
        {"name": "FastAPI", "category": "Frameworks"},
        {"name": "PostgreSQL", "category": "Databases"},
        {"name": "Docker", "category": "DevOps"},
        {"name": "Kubernetes", "category": "DevOps"},
        {"name": "Redis", "category": "Databases"}
    ],
    "experience": [
        {
            "company": "Apex Systems",
            "role": "Senior Software Engineer",
            "start_date": "2021",
            "end_date": "Present",
            "location": "San Francisco, CA",
            "bullets": [
                {
                    "id": "b_apex_1",
                    "text": "Refactored payment gateway microservice, reducing response latency by 1.5s and saving $1,500,000 annually across 10x traffic volume."
                },
                {
                    "id": "b_apex_2",
                    "text": "Architected PostgreSQL distributed read replicas improving read throughput by 35%."
                }
            ]
        }
    ],
    "projects": [
        {
            "name": "TitanRAG",
            "subtitle": "Multi-Tenant Multimodal RAG Platform",
            "technologies": "Python, FastAPI, PostgreSQL, Qdrant, Redis",
            "link": "github.com/alexmercer/titanrag",
            "start_date": "2024",
            "end_date": "Present",
            "bullets": [
                {
                    "id": "b_proj_1",
                    "text": "Engineered multi-tenant multimodal RAG platform with PostgreSQL RLS and Qdrant isolation."
                }
            ]
        }
    ],
    "education": [
        {
            "institution": "University of California, Berkeley",
            "degree": "B.S.",
            "field": "Computer Science",
            "end_date": "2020",
            "gpa": "3.85"
        }
    ],
    "summary": "Senior Software Engineer specializing in high-throughput distributed systems, event-driven architectures, and cloud infrastructure."
}


@router.get("", response_model=MasterProfileResponse)
async def get_master_profile(user_id: str = Depends(get_current_user_id)):
    """
    Retrieves and decrypts the candidate's Master Profile using their tenant-derived HKDF DEK.
    """
    record = encrypted_profiles_db.get(user_id)
    if not record:
        # Initial default profile
        return MasterProfileResponse(
            user_id=user_id,
            version=1,
            profile=MasterProfilePayload(**DEFAULT_SAMPLE_PROFILE),
            updated_at=datetime.now(timezone.utc).isoformat(),
            message="Default initial Master Profile. Edit and save to encrypt in tenant vault."
        )

    # Decrypt AES-256-GCM ciphertext using tenant HKDF key
    decrypted_bytes = EnvelopeEncryption.decrypt(
        ciphertext=record["ciphertext"],
        iv=record["iv"],
        user_id=user_id
    )
    profile_dict = json.loads(decrypted_bytes.decode("utf-8"))

    return MasterProfileResponse(
        user_id=user_id,
        version=record["version"],
        profile=MasterProfilePayload(**profile_dict),
        updated_at=record["updated_at"],
        message="Master Profile decrypted from secure tenant vault."
    )


@router.post("", response_model=MasterProfileResponse, status_code=status.HTTP_200_OK)
async def save_master_profile(
    payload: MasterProfilePayload,
    user_id: str = Depends(get_current_user_id)
):
    """
    Encrypts candidate Master Profile with per-tenant AES-256-GCM HKDF envelope encryption
    and persists into the tenant vault.
    """
    json_bytes = json.dumps(payload.model_dump()).encode("utf-8")
    ciphertext, iv = EnvelopeEncryption.encrypt(json_bytes, user_id=user_id)

    curr_version = encrypted_profiles_db.get(user_id, {}).get("version", 0) + 1
    now_iso = datetime.now(timezone.utc).isoformat()

    encrypted_profiles_db[user_id] = {
        "version": curr_version,
        "ciphertext": ciphertext,
        "iv": iv,
        "updated_at": now_iso
    }
    _save_persisted_profiles()

    logger.info(f"Master Profile for user '{user_id}' encrypted and saved (version {curr_version}).")

    return MasterProfileResponse(
        user_id=user_id,
        version=curr_version,
        profile=payload,
        updated_at=now_iso,
        message="Master Profile successfully encrypted and updated in tenant vault."
    )


@router.post("/parse-resume", response_model=ResumeParseResponse, status_code=status.HTTP_200_OK)
async def parse_resume_json(
    request: ResumeParseRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Parses a base resume (PDF base64 or raw text) into structured MasterProfilePayload.
    Extracts canonical skills via taxonomy, validates bullet points with metrics, and returns structured data.
    """
    try:
        if request.pdf_base64:
            pdf_bytes = base64.b64decode(request.pdf_base64)
            profile_dict = resume_parser.parse_pdf(pdf_bytes)
            raw_text = resume_parser.extract_text_from_pdf(pdf_bytes)
        elif request.raw_text:
            profile_dict = resume_parser.parse_resume_text(request.raw_text)
            raw_text = request.raw_text
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'pdf_base64' or 'raw_text' must be provided."
            )

        logger.info(
            f"Parsed resume for user '{user_id}': detected {len(profile_dict.get('skills', []))} skills, "
            f"{len(profile_dict.get('experience', []))} roles. Details:\n{json.dumps(profile_dict, indent=2)}"
        )

        structured_profile = MasterProfilePayload(**profile_dict)

        return ResumeParseResponse(
            profile=structured_profile,
            detected_skills_count=len(structured_profile.skills),
            detected_experience_count=len(structured_profile.experience),
            raw_text_length=len(raw_text),
            message=f"Resume parsed: detected {len(structured_profile.skills)} skills and {len(structured_profile.experience)} career roles."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse resume document: {str(e)}"
        )


@router.post("/upload-resume-file", response_model=ResumeParseResponse, status_code=status.HTTP_200_OK)
async def upload_resume_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Multipart/form-data file upload endpoint for base resume PDF/text files.
    """
    try:
        content = await file.read()
        if file.filename and file.filename.lower().endswith(".pdf"):
            profile_dict = resume_parser.parse_pdf(content)
            raw_text = resume_parser.extract_text_from_pdf(content)
        else:
            text = content.decode("utf-8", errors="ignore")
            profile_dict = resume_parser.parse_resume_text(text)
            raw_text = text

        structured_profile = MasterProfilePayload(**profile_dict)

        return ResumeParseResponse(
            profile=structured_profile,
            detected_skills_count=len(structured_profile.skills),
            detected_experience_count=len(structured_profile.experience),
            raw_text_length=len(raw_text),
            message=f"Resume '{file.filename}' parsed: detected {len(structured_profile.skills)} skills."
        )
    except Exception as e:
        logger.error(f"Error handling resume file upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse uploaded file: {str(e)}"
        )


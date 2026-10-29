from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class PersonalInfo(BaseModel):
    full_name: str = Field(..., description="Full legal candidate name")
    email: str = Field(..., description="Contact email address")
    phone: Optional[str] = Field("", description="Phone number")
    location: Optional[str] = Field("", description="City, State or Country")
    linkedin: Optional[str] = Field("", description="LinkedIn profile handle or URL")
    github: Optional[str] = Field("", description="GitHub profile handle or URL")


class BulletPoint(BaseModel):
    id: str = Field(..., description="Unique bullet identifier for entailment tracking")
    text: str = Field(..., description="Authentic accomplishment description with metrics")

    @model_validator(mode="before")
    @classmethod
    def normalize_bullet(cls, data: Any) -> Any:
        import uuid
        if isinstance(data, str):
            return {"id": str(uuid.uuid4())[:8], "text": data.strip()}
        if isinstance(data, dict):
            if not data.get("id"):
                data["id"] = str(uuid.uuid4())[:8]
            if not data.get("text"):
                data["text"] = str(data.get("description") or "").strip()
        return data


class ExperienceItem(BaseModel):
    company: str = Field(..., description="Employer name")
    role: str = Field(..., description="Job title / role held")
    start_date: str = Field(..., description="Start date (e.g. 2021)")
    end_date: str = Field(..., description="End date or 'Present'")
    location: Optional[str] = Field("Remote", description="Office location")
    bullets: List[BulletPoint] = Field(default_factory=list, description="Verified accomplishment bullets")

    @model_validator(mode="before")
    @classmethod
    def normalize_experience(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("company"):
                data["company"] = data.get("name") or "Company"
            if not data.get("role"):
                data["role"] = data.get("subtitle") or "Engineer"
            if not data.get("start_date"):
                data["start_date"] = "2021"
            if not data.get("end_date"):
                data["end_date"] = "Present"
        return data


class EducationItem(BaseModel):
    institution: str = Field(..., description="University or educational institution")
    degree: str = Field(..., description="Degree obtained (e.g. B.S., M.S.)")
    field: str = Field(..., description="Field of study / major")
    end_date: Optional[str] = Field("", description="Graduation year")
    gpa: Optional[str] = Field("", description="GPA (optional)")


class ProjectItem(BaseModel):
    name: str = Field(..., description="Project name")
    subtitle: Optional[str] = Field("", description="Project role or subtitle")
    technologies: Optional[str] = Field("", description="Technologies used, comma-separated")
    link: Optional[str] = Field("", description="GitHub or live URL")
    start_date: Optional[str] = Field("2024", description="Start date")
    end_date: Optional[str] = Field("Present", description="End date")
    bullets: List[BulletPoint] = Field(default_factory=list, description="Verified accomplishment bullets")

    @model_validator(mode="before")
    @classmethod
    def normalize_project(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name"):
                data["name"] = data.get("company") or data.get("title") or "Featured Project"
            if not data.get("subtitle") and data.get("role"):
                data["subtitle"] = data.get("role")
        return data


class SkillItem(BaseModel):
    name: str = Field(..., description="Skill / technology name")
    category: Optional[str] = Field("General", description="Category (e.g. Languages, Databases)")


class Preferences(BaseModel):
    legally_authorized: Optional[bool] = Field(True, description="Legally authorized to work in target country")
    requires_sponsorship: Optional[bool] = Field(False, description="Requires visa sponsorship now or in the future")
    gender: Optional[str] = Field("", description="EEO Gender disclosure")
    veteran_status: Optional[str] = Field("", description="EEO Veteran status")
    disability_status: Optional[str] = Field("", description="EEO Disability status")


class MasterProfilePayload(BaseModel):
    personal: PersonalInfo
    skills: List[SkillItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list, description="Personal or featured technical projects")
    education: List[EducationItem] = Field(default_factory=list)
    summary: Optional[str] = Field("", description="Candidate master bio / summary")
    section_order: Optional[List[str]] = Field(default=None, description="Preserved section ordering from base resume")
    preferences: Optional[Preferences] = Field(default_factory=Preferences, description="Work auth & EEO preferences")


class MasterProfileResponse(BaseModel):
    user_id: str
    version: int
    profile: MasterProfilePayload
    updated_at: str
    message: str = "Master Profile saved and encrypted with tenant HKDF key."


class ResumeParseRequest(BaseModel):
    pdf_base64: Optional[str] = Field(None, description="Base64-encoded PDF resume file")
    raw_text: Optional[str] = Field(None, description="Raw resume text if parsing text directly")


class ResumeParseResponse(BaseModel):
    profile: MasterProfilePayload
    detected_skills_count: int
    detected_experience_count: int
    raw_text_length: int
    message: str = "Base resume parsed and structured successfully."


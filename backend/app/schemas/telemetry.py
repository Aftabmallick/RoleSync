from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SelectorFailureReport(BaseModel):
    host: str = Field(..., description="Target domain or hostname, e.g. 'jobs.lever.co'")
    ats_provider: str = Field(..., description="Identified provider: GREENHOUSE, LEVER, WORKDAY, LINKEDIN, GENERIC")
    failed_selectors: List[str] = Field(..., description="List of CSS or XPath selectors that failed to match")
    page_structure_summary: Dict[str, Any] = Field(
        ...,
        description="Sanitized structural summary (tag counts, depth, candidate text lengths). Strictly zero PII."
    )
    client_version: str = Field(..., description="Chrome extension or SDK client version")
    timestamp: Optional[float] = Field(None, description="Client UNIX timestamp")


class SelectorFailureResponse(BaseModel):
    status: str = "RECORDED"
    report_id: str
    action_taken: str = "Queued for selector registry self-healing"
    message: str = "Telemetry recorded. Drift monitoring alerted."


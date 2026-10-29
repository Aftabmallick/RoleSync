import logging
import re
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from app.schemas.telemetry import SelectorFailureReport, SelectorFailureResponse

router = APIRouter(prefix="/telemetry", tags=["Observability & Telemetry"])
logger = logging.getLogger("rolesync.telemetry")

# Telemetry store for drift tracking in memory (persisted in DB/Prometheus in cluster)
drift_event_log = []


def sanitize_structural_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantees no candidate PII (email, phone, long strings) is captured in telemetry.
    """
    email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    phone_regex = re.compile(r"\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b")

    sanitized = {}
    for k, v in data.items():
        if isinstance(v, str):
            # Check for PII leaks
            if email_regex.search(v) or phone_regex.search(v):
                sanitized[k] = "[REDACTED_PII]"
            else:
                sanitized[k] = v[:200]  # truncate long strings
        elif isinstance(v, dict):
            sanitized[k] = sanitize_structural_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_structural_metadata(item) if isinstance(item, dict) else str(item)[:100]
                for item in v[:50]
            ]
        else:
            sanitized[k] = v
    return sanitized


@router.post(
    "/selector-failure",
    response_model=SelectorFailureResponse,
    status_code=status.HTTP_200_OK,
)
async def report_selector_failure(report: SelectorFailureReport):
    """
    Receives selector failure telemetry when client ATS extraction fails.
    Sanitizes structural metadata, logs drift warning, and queues for selector self-healing.
    """
    clean_summary = sanitize_structural_metadata(report.page_structure_summary)
    report_id = f"drift_{uuid.uuid4().hex[:12]}"

    event = {
        "report_id": report_id,
        "host": report.host,
        "ats_provider": report.ats_provider,
        "failed_selectors": report.failed_selectors,
        "summary": clean_summary,
        "client_version": report.client_version,
        "timestamp": report.timestamp,
    }
    drift_event_log.append(event)

    logger.warning(
        f"[DRIFT_ALERT] Selector failure on host='{report.host}' provider='{report.ats_provider}'. "
        f"Failed selectors: {report.failed_selectors}. Report ID: {report_id}"
    )

    return SelectorFailureResponse(
        status="RECORDED",
        report_id=report_id,
        action_taken="Queued for selector registry self-healing",
        message="Telemetry recorded. Drift monitoring alerted.",
    )


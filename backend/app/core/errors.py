import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """
    RFC 7807 Standard Problem Details for HTTP APIs (application/problem+json).
    """
    type: str = Field("about:blank", description="URI reference identifying the problem type")
    title: str = Field(..., description="Short, human-readable summary of problem")
    status: int = Field(..., description="HTTP status code")
    detail: Optional[str] = Field(None, description="Human-readable explanation specific to this occurrence")
    instance: str = Field(..., description="URI reference identifying specific occurrence of the problem")
    invalid_params: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed validation breakdown")


class RoleSyncException(Exception):
    """Base exception for application-level domain errors."""
    def __init__(self, title: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST, error_type: str = "about:blank"):
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.error_type = error_type


class ResourceNotFoundException(RoleSyncException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            title="Resource Not Found",
            detail=f"{resource} '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="https://rolesync.ai/errors/resource-not-found"
        )


class SelectorDriftException(RoleSyncException):
    def __init__(self, provider: str, details: str):
        super().__init__(
            title="ATS Selector Drift Detected",
            detail=f"DOM layout change detected on {provider}: {details}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="https://rolesync.ai/errors/selector-drift"
        )


def register_problem_handlers(app: FastAPI) -> None:
    """
    Mounts RFC 7807 compliant exception handlers to FastAPI application.
    """
    @app.exception_handler(RoleSyncException)
    async def handle_rolesync_exception(request: Request, exc: RoleSyncException):
        instance_id = f"urn:rolesync:error:{uuid.uuid4().hex}"
        problem = ProblemDetail(
            type=exc.error_type,
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            instance=f"{request.url.path}#{instance_id}",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        instance_id = f"urn:rolesync:error:{uuid.uuid4().hex}"
        problem = ProblemDetail(
            type="https://rolesync.ai/errors/http-error",
            title="HTTP Request Error",
            status=exc.status_code,
            detail=str(exc.detail),
            instance=f"{request.url.path}#{instance_id}",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        instance_id = f"urn:rolesync:error:{uuid.uuid4().hex}"
        invalid_params = []
        for err in exc.errors():
            invalid_params.append({
                "name": ".".join(str(loc) for loc in err.get("loc", [])),
                "reason": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            })

        problem = ProblemDetail(
            type="https://rolesync.ai/errors/validation-error",
            title="Unprocessable Request Payload",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request payload failed structural validation checks.",
            instance=f"{request.url.path}#{instance_id}",
            invalid_params=invalid_params,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )


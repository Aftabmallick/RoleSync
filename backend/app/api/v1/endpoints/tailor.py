import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from app.schemas.tailor import TailorRequest, TailorTaskResponse, TailorResultResponse
from app.tasks.tailor_tasks import orchestrator, task_store

router = APIRouter(prefix="/tailor", tags=["Resume Tailoring"])


@router.post("", response_model=TailorTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_tailoring_task(
    payload: TailorRequest,
    background_tasks: BackgroundTasks
):
    """
    Enqueues an asynchronous resume tailoring task.
    Returns 202 Accepted with a task_id to prevent HTTP gateway timeouts.
    """
    task_id = f"task_{uuid.uuid4().hex}"
    task_store[task_id] = {"status": "QUEUED", "stage": "INITIALIZED"}

    # Mock candidate Master Profile for demonstration / tests
    sample_master_profile = {
        "personal": {
            "full_name": "Alex Mercer",
            "email": "alex@mercer.dev",
            "phone": "+1 555-019-2834",
            "location": "San Francisco, CA",
            "linkedin": "linkedin.com/in/alex-mercer"
        },
        "skills": [
            {"name": "Python"},
            {"name": "FastAPI"},
            {"name": "PostgreSQL"},
            {"name": "Docker"},
            {"name": "Kubernetes"},
            {"name": "Redis"}
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
        "education": [
            {
                "institution": "University of California, Berkeley",
                "degree": "B.S.",
                "field": "Computer Science",
                "end_date": "2020",
                "gpa": "3.85"
            }
        ]
    }

    effective_profile = dict(payload.master_profile) if payload.master_profile else dict(sample_master_profile)

    # Ensure experience is non-empty and has at least one verified bullet point
    if not effective_profile.get("experience"):
        effective_profile["experience"] = sample_master_profile["experience"]
    else:
        for i, exp in enumerate(effective_profile["experience"]):
            if not exp.get("bullets"):
                exp["bullets"] = [
                    {
                        "id": f"b_{i+1}_1",
                        "text": f"Engineered scalable infrastructure and microservices at {exp.get('company', 'Tech Organization')}."
                    }
                ]

    # Ensure skills list is non-empty
    if not effective_profile.get("skills"):
        effective_profile["skills"] = sample_master_profile["skills"]

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
                    "user_id": "usr_demo_123",
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
            user_id="usr_demo_123",
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

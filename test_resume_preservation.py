import json
import base64
import requests
import time
import io
import fitz  # PyMuPDF to inspect compiled PDF text

API_BASE = "http://localhost:8000/api/v1"

# A complete candidate resume with all sections
SAMPLE_FULL_PROFILE = {
    "personal": {
        "full_name": "Jordan Hayes",
        "email": "jordan.hayes@example.com",
        "phone": "+1 (555) 019-2834",
        "location": "San Francisco, CA",
        "linkedin": "linkedin.com/in/jordan-hayes",
        "github": "github.com/jordanhayes"
    },
    "summary": "Senior Software Architect specializing in fault-tolerant distributed systems, event-driven pipelines, and cloud-native Kubernetes infrastructure.",
    "skills": [
        {"name": "Python", "category": "Languages"},
        {"name": "Go", "category": "Languages"},
        {"name": "FastAPI", "category": "Frameworks"},
        {"name": "PostgreSQL", "category": "Databases"},
        {"name": "Docker", "category": "DevOps"},
        {"name": "Kubernetes", "category": "DevOps"},
        {"name": "Redis", "category": "Databases"},
        {"name": "Kafka", "category": "Messaging"},
        {"name": "AWS", "category": "Cloud"},
        {"name": "Terraform", "category": "DevOps"},
        {"name": "Distributed Systems", "category": "Architecture"}
    ],
    "experience": [
        {
            "company": "TechFlow Systems",
            "role": "Staff Platform Engineer",
            "start_date": "2021",
            "end_date": "Present",
            "location": "San Francisco, CA",
            "bullets": [
                {
                    "id": "exp_b1",
                    "text": "Refactored payment gateway microservice, reducing response latency by 1.5s and saving $1,500,000 annually across 10x traffic volume."
                },
                {
                    "id": "exp_b2",
                    "text": "Architected PostgreSQL distributed read replicas improving query throughput by 35% with zero downtime."
                }
            ]
        },
        {
            "company": "Acme Cloud",
            "role": "Senior Backend Developer",
            "start_date": "2018",
            "end_date": "2021",
            "location": "Remote",
            "bullets": [
                {
                    "id": "exp_b3",
                    "text": "Engineered real-time telemetry streaming service handling 50,000 events/sec via Redis and Kafka."
                }
            ]
        }
    ],
    "projects": [
        {
            "name": "CloudSync Engine",
            "subtitle": "Multi-Tenant Multimodal RAG Platform",
            "technologies": "Python, FastAPI, PostgreSQL (RLS), Qdrant, Celery, Redis",
            "link": "github.com/jordanhayes/cloudsync",
            "start_date": "2024",
            "end_date": "Present",
            "bullets": [
                {
                    "id": "proj_b1",
                    "text": "Engineered a multi-tenant multimodal RAG platform leveraging PostgreSQL Row-Level Security and tenant-isolated collections in Qdrant."
                }
            ]
        }
    ],
    "education": [
        {
            "institution": "University of California, Berkeley",
            "degree": "B.S.",
            "field": "Computer Science",
            "end_date": "2018",
            "gpa": "3.85"
        }
    ],
    "section_order": ["Summary", "Technical Skills", "Work Experience", "Featured Projects", "Education"]
}

JOB_DESCRIPTION = """
We are looking for a Senior Infrastructure & Backend Engineer at Stripe to build high-scale payment pipelines.
Required skills: Python, FastAPI, Docker, Kubernetes, PostgreSQL, Distributed Systems.
Experience designing fault-tolerant low-latency microservices is essential.
"""

def test_tailoring_preservation():
    print(">>> 1. Enqueueing Resume Tailoring Pipeline...")
    res = requests.post(
        f"{API_BASE}/tailor",
        json={
            "target_role": "Senior Infrastructure Engineer",
            "company_name": "Stripe",
            "raw_job_description": JOB_DESCRIPTION,
            "required_years": 4.0,
            "master_profile": SAMPLE_FULL_PROFILE
        },
        timeout=10
    )
    assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
    task_id = res.json()["task_id"]
    print(f"    Task enqueued successfully: task_id={task_id}")

    print(">>> 2. Polling Task Execution Status...")
    tailor_result = None
    for attempt in range(30):
        time.sleep(1)
        poll_res = requests.get(f"{API_BASE}/tailor/{task_id}", timeout=10)
        assert poll_res.status_code == 200, f"Poll failed: {poll_res.text}"
        data = poll_res.json()
        print(f"    [Poll {attempt+1}] Status: {data.get('status')}")
        if data.get("status") == "COMPLETED":
            tailor_result = data
            break
        elif data.get("status") == "FAILED":
            raise RuntimeError(f"Tailoring pipeline failed: {data.get('error')}")

    assert tailor_result is not None, "Task did not complete within timeout window."
    draft = tailor_result.get("tailored_draft")
    assert draft is not None, "tailored_draft is None"

    print("\n>>> 3. Verifying Resume Section Content Preservation in Draft...")
    
    # 3.1 Check Summary Preservation
    assert "fault-tolerant distributed systems" in draft["summary"], (
        f"Original authentic summary was overwritten! Found: {draft['summary']}"
    )
    print("    [PASS] Authentic summary preserved without generic overwrite.")

    # 3.2 Check Experience Chronology
    companies_order = [e["company"] for e in draft["experience"]]
    assert companies_order == ["TechFlow Systems", "Acme Cloud"], (
        f"Experience ordering was scrambled! Found: {companies_order}"
    )
    print("    [PASS] Chronological work experience ordering strictly preserved.")

    # 3.3 Check Experience Bullets
    total_bullets = sum(len(e["bullet_points"]) for e in draft["experience"])
    assert total_bullets == 3, f"Expected 3 experience bullets, got {total_bullets}"
    print(f"    [PASS] All {total_bullets} experience bullets preserved.")

    # 3.4 Check Projects Preservation
    projects = draft.get("projects") or []
    assert len(projects) == 1, f"Expected 1 project in draft, got {len(projects)}"
    assert projects[0]["name"] == "CloudSync Engine", f"Project name mismatch: {projects[0]}"
    print("    [PASS] Featured projects fully preserved in tailored draft.")

    # 3.5 Check Education Preservation
    education = draft.get("education") or []
    assert len(education) == 1, f"Expected 1 education entry in draft, got {len(education)}"
    assert education[0]["institution"] == "University of California, Berkeley"
    print("    [PASS] Education fully preserved in tailored draft.")

    # 3.6 Check Skills Preservation
    skills = draft.get("skills") or []
    assert len(skills) >= 11, f"Skills were truncated! Expected >= 11, got {len(skills)}"
    print(f"    [PASS] All {len(skills)} candidate skills preserved.")

    print("\n>>> 4. Verifying Typst Vector PDF Document...")
    pdf_b64 = tailor_result.get("pdf_base64")
    assert pdf_b64, "Compiled PDF is missing from result payload."
    pdf_bytes = base64.b64decode(pdf_b64)
    assert len(pdf_bytes) > 1000, f"PDF bytes unexpectedly small: {len(pdf_bytes)}"

    # Parse text from PDF using PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) == 1, f"Expected single-page PDF, got {len(doc)} pages"
    pdf_text = doc[0].get_text()

    print("    Extracted PDF Text Sample:")
    for line in pdf_text.split("\n")[:15]:
        if line.strip():
            print(f"      | {line.strip()}")

    # Verify all 5 core sections are present in compiled PDF
    assert "Jordan Hayes" in pdf_text, "Candidate name missing from PDF"
    assert "TechFlow Systems" in pdf_text, "Experience (TechFlow Systems) missing from PDF"
    assert "Acme Cloud" in pdf_text, "Experience (Acme Cloud) missing from PDF"
    assert "CloudSync Engine" in pdf_text, "Featured Project (CloudSync Engine) missing from PDF"
    assert "University of California, Berkeley" in pdf_text, "Education (UC Berkeley) missing from PDF"
    assert "Python" in pdf_text, "Technical Skills missing from PDF"

    print("\n[SUCCESS] ALL RESUME SECTIONS VERIFIED PRESERVED IN DRAFT AND COMPILED VECTOR PDF!")

if __name__ == "__main__":
    test_tailoring_preservation()


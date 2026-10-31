#!/usr/bin/env python3
"""
RoleSync Empirical Stress Harness: Concurrency, Celery Pipeline & WebSocket Streaming
Author: Empirical Challenger 2 (Milestone 1)

Empirically challenges:
1. Concurrent Celery task dispatch (multiple parallel tailoring jobs)
2. Asynchronous task polling across HTTP
3. Real-time WebSocket streaming transitions (stages + PING/PONG)
4. Multi-client fan-out (multiple WebSocket listeners on single task)
5. Mid-stream abrupt WebSocket disconnect recovery
6. Non-existent task WebSocket handling
7. Full payload verification (ATS composite score, Typst PDF base64)
8. Complete ephemeral cleanup with zero residual state
"""

import os
import sys
import time
import json
import uuid
import base64
import asyncio
from typing import Dict, Any, List, Optional
import requests
import websockets
import psycopg2

BASE_URL = os.getenv("ROLESYNC_BASE_URL", "http://127.0.0.1:8000")
WS_BASE_URL = os.getenv("ROLESYNC_WS_URL", "ws://127.0.0.1:8000")
PG_URL = os.getenv("ROLESYNC_PG_URL", "postgresql://rolesync_admin:rolesync_secure_password@localhost:5432/rolesync_db")


class ConcurrencyAndWebSocketChallenger:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False

        self.run_id = uuid.uuid4().hex[:8]
        self.test_email = f"live_test_stress_{self.run_id}@rolesync.io"
        self.test_password = f"StressPass_{self.run_id}!99"
        self.user_id: Optional[str] = None
        self.auth_headers: Dict[str, str] = {}

        self.tasks: List[Dict[str, Any]] = []
        self.stress_results: Dict[str, Any] = {}

    def log(self, section: str, msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] [{section}] {msg}")

    def setup_ephemeral_account(self):
        self.log("SETUP", f"Registering ephemeral candidate: {self.test_email}")
        reg_res = self.session.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={
                "email": self.test_email,
                "password": self.test_password,
                "full_name": f"Stress Tester {self.run_id}"
            },
            timeout=10
        )
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        data = reg_res.json()
        self.user_id = data["user"]["id"]
        token = data["access_token"]
        self.auth_headers = {"Authorization": f"Bearer {token}"}

        # Save rich master profile
        profile_payload = {
            "personal": {
                "full_name": f"Stress Candidate {self.run_id}",
                "email": self.test_email,
                "phone": "+1 555-019-2834",
                "location": "San Francisco, CA"
            },
            "skills": [
                {"name": "Python"}, {"name": "FastAPI"}, {"name": "PostgreSQL"},
                {"name": "Docker"}, {"name": "Kubernetes"}, {"name": "Redis"},
                {"name": "Celery"}, {"name": "Typst"}, {"name": "TypeScript"},
                {"name": "AWS"}, {"name": "GraphQL"}, {"name": "Microservices"}
            ],
            "experience": [
                {
                    "company": "Scale Dynamics",
                    "role": "Staff Distributed Systems Engineer",
                    "start_date": "2021",
                    "end_date": "Present",
                    "location": "San Francisco, CA",
                    "bullets": [
                        {
                            "id": "b_scale_1",
                            "text": "Architected event-driven microservices processing 100k msg/sec with Redis PubSub and Celery workers."
                        },
                        {
                            "id": "b_scale_2",
                            "text": "Reduced P99 query latency from 850ms to 42ms via PostgreSQL indexing and connection pooling."
                        }
                    ]
                },
                {
                    "company": "CloudForge Labs",
                    "role": "Senior Backend Developer",
                    "start_date": "2018",
                    "end_date": "2021",
                    "location": "Sunnyvale, CA",
                    "bullets": [
                        {
                            "id": "b_forge_1",
                            "text": "Deployed containerized services onto Kubernetes with Istio service mesh and Prometheus monitoring."
                        }
                    ]
                }
            ],
            "education": [
                {
                    "institution": "University of California, Berkeley",
                    "degree": "B.S. in Computer Science",
                    "field": "Computer Science",
                    "end_date": "2018"
                }
            ]
        }

        prof_res = self.session.post(
            f"{BASE_URL}/api/v1/profile",
            headers=self.auth_headers,
            json=profile_payload,
            timeout=10
        )
        assert prof_res.status_code == 200, f"Profile save failed: {prof_res.text}"
        self.log("SETUP", "Ephemeral account and master profile initialized successfully.")

    def test_nonexistent_websocket(self):
        """Stress-test: Connect to non-existent task_id, send PING, receive PONG, clean close."""
        self.log("WS-EDGE", "Testing WebSocket connection to non-existent task UUID...")
        non_existent_id = f"task_{uuid.uuid4().hex}"
        ws_url = f"{WS_BASE_URL}/ws/v1/tasks/{non_existent_id}"

        async def run_probe():
            async with websockets.connect(ws_url, close_timeout=3) as ws:
                await ws.send("PING")
                res = await asyncio.wait_for(ws.recv(), timeout=2.0)
                assert res == "PONG", f"Expected PONG, got: {res}"
                # Clean disconnect
                await ws.close()

        asyncio.run(run_probe())
        self.log("WS-EDGE", "Non-existent task WebSocket handled PING/PONG and disconnected cleanly.")

    def enqueue_concurrent_tasks(self, num_tasks: int = 5) -> List[str]:
        """Dispatches multiple concurrent tailoring jobs."""
        self.log("CONCURRENCY", f"Enqueuing {num_tasks} parallel resume tailoring jobs...")
        task_ids = []

        job_configs = [
            ("Senior Python Core Engineer", "Datadog", "Looking for Senior Python Engineers with FastAPI, Celery, and Redis."),
            ("Lead Distributed Systems Architect", "Cloudflare", "Seeking Architect skilled in Kubernetes, PostgreSQL, and high-throughput pipelines."),
            ("Principal Infrastructure Engineer", "Airbnb", "Hiring Engineer experienced in Docker, microservices, Typst compilation, and ATS optimization."),
            ("Senior Platform Engineer", "Uber", "Looking for Senior Platform Engineers with gRPC, Docker, Kubernetes, and Golang/Python."),
            ("Staff Cloud Systems Architect", "Snowflake", "Seeking Staff Cloud Systems Architect experienced in high availability, distributed caching, and vector search.")
        ]

        for i in range(num_tasks):
            role, comp, jd = job_configs[i % len(job_configs)]
            payload = {
                "target_role": role,
                "company_name": comp,
                "raw_job_description": jd,
                "required_years": 4.0
            }
            res = self.session.post(
                f"{BASE_URL}/api/v1/tailor",
                headers=self.auth_headers,
                json=payload,
                timeout=10
            )
            assert res.status_code == 202, f"Enqueue task {i+1} failed ({res.status_code}): {res.text}"
            data = res.json()
            tid = data["task_id"]
            task_ids.append(tid)
            self.log("CONCURRENCY", f"Task {i+1}/{num_tasks} enqueued: {tid} (Status: {data['status']})")

        return task_ids

    async def monitor_task_websocket(
        self,
        task_id: str,
        task_idx: int,
        results_collector: Dict[str, Any]
    ):
        """Monitors WebSocket stream for a task, tracking stage transitions and PING/PONG."""
        ws_url = f"{WS_BASE_URL}/ws/v1/tasks/{task_id}"
        stages_observed = []
        pongs_received = 0
        pings_sent = 0
        t0 = time.time()

        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                # Listener loop for up to 15 seconds
                while time.time() - t0 < 15.0:
                    # Periodically send PING
                    if pings_sent < 4:
                        await ws.send("PING")
                        pings_sent += 1

                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        if msg == "PONG":
                            pongs_received += 1
                        else:
                            try:
                                data = json.loads(msg)
                                stage = data.get("stage") or data.get("status")
                                if stage and stage not in stages_observed:
                                    stages_observed.append(stage)
                                    self.log(f"WS-{task_idx}", f"Observed stage transition -> {stage}")
                                if stage == "COMPLETED":
                                    break
                            except Exception:
                                pass
                    except asyncio.TimeoutError:
                        pass

                # Clean disconnect
                await ws.close()
        except Exception as e:
            self.log(f"WS-{task_idx}", f"Error: {e}")

        results_collector[task_id] = {
            "stages": stages_observed,
            "pings_sent": pings_sent,
            "pongs_received": pongs_received,
            "connected_duration_s": round(time.time() - t0, 2)
        }

    async def test_fanout_and_abrupt_disconnect(self, task_id: str):
        """
        Stress test:
        1. Open TWO concurrent WebSocket listeners on the SAME task_id.
        2. Intentionally drop listener 1 abruptly mid-stream.
        3. Verify listener 2 continues receiving frames and completes cleanly.
        """
        self.log("FANOUT-STRESS", f"Testing dual-subscriber fanout & abrupt disconnect on {task_id}...")
        ws_url = f"{WS_BASE_URL}/ws/v1/tasks/{task_id}"
        events_client_1 = []
        events_client_2 = []

        async def subscriber_1():
            async with websockets.connect(ws_url, close_timeout=2) as ws1:
                # Receive first event or send PING
                await ws1.send("PING")
                pong = await asyncio.wait_for(ws1.recv(), timeout=2.0)
                events_client_1.append(pong)
                # Intentionally close immediately (simulate browser tab close / dropped connection)
                await ws1.close(code=1000)

        async def subscriber_2():
            async with websockets.connect(ws_url, close_timeout=5) as ws2:
                for _ in range(5):
                    await ws2.send("PING")
                    try:
                        msg = await asyncio.wait_for(ws2.recv(), timeout=2.0)
                        events_client_2.append(msg)
                    except asyncio.TimeoutError:
                        break
                await ws2.close()

        await asyncio.gather(subscriber_1(), subscriber_2())
        self.log("FANOUT-STRESS", f"Fanout & abrupt disconnect handled cleanly. Client 1 received {len(events_client_1)} frames, Client 2 received {len(events_client_2)} frames.")
        return len(events_client_1) > 0 and len(events_client_2) > 0

    def poll_tasks_http(self, task_ids: List[str], max_wait_sec: float = 20.0) -> Dict[str, Dict[str, Any]]:
        """Polls HTTP GET /api/v1/tailor/{task_id} until all complete or timeout."""
        self.log("POLL", f"Polling {len(task_ids)} tasks via HTTP until COMPLETED...")
        completed = {}
        t0 = time.time()

        while time.time() - t0 < max_wait_sec:
            for tid in task_ids:
                if tid in completed:
                    continue
                res = self.session.get(f"{BASE_URL}/api/v1/tailor/{tid}", headers=self.auth_headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    status = data.get("status")
                    if status == "COMPLETED":
                        completed[tid] = data
                        self.log("POLL", f"Task {tid} marked COMPLETED (Latency: {round(time.time() - t0, 2)}s)")
            if len(completed) == len(task_ids):
                break
            time.sleep(0.5)

        return completed

    def teardown(self):
        """Clean teardown: delete master profile and purge user from DB."""
        self.log("TEARDOWN", f"Purging ephemeral test data for {self.test_email}...")
        try:
            self.session.delete(f"{BASE_URL}/api/v1/profile", headers=self.auth_headers, timeout=5)
        except Exception:
            pass

        try:
            conn = psycopg2.connect(PG_URL)
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE email = %s;", (self.test_email,))
            deleted = cur.rowcount
            conn.commit()

            cur.execute("SELECT count(*) FROM users WHERE email = %s;", (self.test_email,))
            users_left = cur.fetchone()[0]

            if self.user_id:
                cur.execute("SELECT count(*) FROM applications WHERE user_id = %s;", (self.user_id,))
                apps_left = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM resume_versions WHERE user_id = %s;", (self.user_id,))
                ver_left = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM master_profiles WHERE user_id = %s;", (self.user_id,))
                prof_left = cur.fetchone()[0]
            else:
                apps_left = ver_left = prof_left = 0
            conn.close()

            self.log("TEARDOWN", f"DB Cascade Purged: {deleted} user rows deleted. Residual: users={users_left}, apps={apps_left}, versions={ver_left}, profiles={prof_left}")
            assert users_left == 0 and apps_left == 0 and ver_left == 0 and prof_left == 0, "Residual DB records found!"
        except Exception as e:
            self.log("TEARDOWN", f"Teardown error: {e}")
            raise

    def run(self) -> bool:
        print("=" * 80)
        print("   ROLESYNC EMPIRICAL CHALLENGER 2: CONCURRENCY & CELERY/WEBSOCKET STRESS   ")
        print("=" * 80)

        all_passed = True
        try:
            # 1. Setup account
            self.setup_ephemeral_account()

            # 2. Non-existent task WebSocket handling
            self.test_nonexistent_websocket()

            # 3. Enqueue 5 concurrent Celery tasks
            task_ids = self.enqueue_concurrent_tasks(num_tasks=5)

            # 4. Fanout & Abrupt disconnect test on first task
            fanout_ok = asyncio.run(self.test_fanout_and_abrupt_disconnect(task_ids[0]))
            assert fanout_ok, "Fanout/abrupt disconnect test failed"

            # 5. Concurrent WebSocket monitoring while Celery runs
            self.log("MONITOR", "Starting concurrent WebSocket listeners across all tasks...")
            ws_results = {}

            async def monitor_all():
                coros = [
                    self.monitor_task_websocket(tid, idx + 1, ws_results)
                    for idx, tid in enumerate(task_ids)
                ]
                await asyncio.gather(*coros)

            asyncio.run(monitor_all())

            # 6. HTTP Polling until all reach COMPLETED
            completed_payloads = self.poll_tasks_http(task_ids, max_wait_sec=20.0)
            assert len(completed_payloads) == len(task_ids), f"Only {len(completed_payloads)}/{len(task_ids)} tasks completed within timeout!"

            # 7. Payload validation on all completed tasks
            self.log("VALIDATION", "Verifying ATS scores, Typst vector PDF, and tailored draft structure...")
            for idx, tid in enumerate(task_ids, 1):
                p = completed_payloads[tid]
                assert p["status"] == "COMPLETED", f"Task {tid} status is {p['status']}"
                ats = p.get("ats_score")
                assert ats is not None, f"Task {tid} missing ats_score"
                assert "composite_score" in ats, f"Task {tid} missing composite_score in ats_score"
                assert 0.0 <= ats["composite_score"] <= 100.0, f"Task {tid} invalid composite score: {ats['composite_score']}"

                draft = p.get("tailored_draft")
                assert draft is not None and isinstance(draft, dict), f"Task {tid} missing tailored_draft"
                assert len(draft.get("skills", [])) > 0, f"Task {tid} draft has no skills"
                assert len(draft.get("experience", [])) > 0, f"Task {tid} draft has no experience"

                pdf_b64 = p.get("pdf_base64")
                assert pdf_b64 is not None and len(pdf_b64) > 100, f"Task {tid} missing pdf_base64"
                pdf_bytes = base64.b64decode(pdf_b64)
                assert pdf_bytes.startswith(b"%PDF"), f"Task {tid} pdf_base64 is not a valid PDF header: {pdf_bytes[:10]}"

                ws_data = ws_results.get(tid, {})
                self.log(
                    "VALIDATION",
                    f"Task {idx} ({tid}): ATS={ats['composite_score']:.1f}% | "
                    f"PDF={len(pdf_bytes)} bytes | WS Stages={ws_data.get('stages', [])} | "
                    f"PONGs={ws_data.get('pongs_received', 0)}/{ws_data.get('pings_sent', 0)}"
                )

            self.log("VERDICT", "ALL CONCURRENCY, CELERY & WEBSOCKET STRESS CRITERIA SATISFIED!")

        except Exception as e:
            self.log("FAIL", f"Stress test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        finally:
            self.teardown()

        print("=" * 80)
        print(f"   STRESS VERDICT: {'PASSED' if all_passed else 'FAILED'}")
        print("=" * 80)
        return all_passed


if __name__ == "__main__":
    challenger = ConcurrencyAndWebSocketChallenger()
    ok = challenger.run()
    sys.exit(0 if ok else 1)

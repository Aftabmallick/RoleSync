# RoleSync

> **Autonomous AI Job Application Copilot & ATS Orchestration Platform**  
> Real-time ATS optimization, zero-hallucination resume tailoring, and DOM automation across Workday, Greenhouse, Lever, and LinkedIn.

---

## Overview

**RoleSync** is an enterprise-grade client-server ecosystem engineered to eliminate recruitment application friction while adhering strictly to modern Applicant Tracking System (ATS) parsing standards.

Operating on a **Dual-Engine Model**:
- **Copilot Mode (Human-in-the-Loop - Default)**: Inline contextual assistant via a Manifest V3 Chrome Extension Side Panel. Parses target Job Descriptions (JDs), benchmarks compatibility across 4 mathematical dimensions, generates strictly entailed resume adaptations with mathematical anti-hallucination guarantees, and populates form elements under user confirmation.
- **Autopilot Mode (Supervised Autonomous)**: Traverses multi-page applicant portals, populates screening responses according to user-defined policy boundaries, dynamically compiles Typst-based vector PDFs calibrated to a single-page budget, binds binary file uploads via the browser's `DataTransfer` API, and executes submission handshakes with exponential backoff and anti-detection heuristics.

---

## Architectural Pillars

- **Zero-Hallucination Mathematical Guarantee**: A 4-layer validation pipeline combining strict structural schemas, canonical skill graph normalization, quantized ONNX NLI entailment verification, and unit-normalized metric bounds guarantees that no claim can appear on a tailored resume unless factually entailed by the candidate's Master Profile.
- **Isomorphic Human Emulation & Framework Interception**: Synthetic DOM dispatch engines intercept native prototype value setters (`HTMLInputElement.prototype.value`) to bypass React/Angular state-shadowing, while reproducing natural Gaussian keystroke jitter, cubic Bezier pointer trajectories, and dynamic `DataTransfer` file uploads.
- **ATS-Native Typst Compilation with Single-Page Budgeting**: Replaces slow LaTeX engines and imprecise HTML-to-canvas converters with a native Rust-based Typst binary compiler executing in <250ms latency. An automated iterative budget optimizer dynamically regulates line spacing, font size, and margins to guarantee strict single-page compliance.
- **Zero-Trust Multi-Tenancy & Transactional RLS**: User data is encrypted at rest using AES-256-GCM with per-tenant HKDF keys. Cross-tenant isolation is enforced at the PostgreSQL database engine layer via transaction-scoped Row-Level Security (RLS) managed by connection pool lifecycle listeners.

---

## Repository Structure

```
RoleSync/
├── backend/
│   ├── alembic/                    # Database migrations & PostgreSQL RLS DDL
│   ├── app/
│   │   ├── api/v1/                 # FastAPI REST & WebSocket endpoints
│   │   ├── core/                   # Security, DB connection pool & JWT logic
│   │   ├── models/                 # SQLAlchemy 2.0 async database models
│   │   ├── schemas/                # Pydantic v2 data contracts
│   │   ├── services/               # Typst compiler, Vector store & Auth services
│   │   ├── templates/              # ATS US-Letter Typst resume template
│   │   └── main.py                 # FastAPI application entrypoint
│   ├── tests/                      # Unit & integration test suites
│   └── requirements.txt
│
└── extension/
    ├── manifest.json               # Chrome Manifest V3 declaration
    ├── src/
    │   ├── background/             # Ephemeral worker & Keepalive port manager
    │   ├── content/                # Content scripts & DOM injectors
    │   ├── sidepanel/              # React 18 / Tailwind CSS Side Panel UI
    │   ├── store/                  # Zustand session state management
    │   └── types/                  # Discriminated union message protocols
    ├── package.json
    └── vite.config.ts
```

---

## Getting Started

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Unit & Integration Tests
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"

# Start Development Server
uvicorn app.main:app --reload --port 8000
```

### Chrome Extension Setup

```bash
cd extension
npm install
npm run build

# Load into Google Chrome:
# 1. Navigate to chrome://extensions/
# 2. Enable "Developer mode" (top right)
# 3. Click "Load unpacked" and select the RoleSync/extension/dist folder
```

---

## Documentation

- [Full Architecture Specification v2.0](ARCHITECTURE_V2.md)
- [Implementation Plan & Roadmap](IMPLEMENTATION_PLAN.md)

---

## License

Apache-2.0

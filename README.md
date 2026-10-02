# Smart Enterprise Applicant Tracking System (ATS)

An enterprise-grade, B2B multi-tenant Applicant Tracking System (ATS) engineered with Natural Language Processing (NLP) to parse, rank, and intelligently match candidate profiles against job requisitions with customizable multi-stage recruitment pipelines.

---

## 🏛️ System Architecture

```text
               ┌──────────────────────────────────────────────┐
               │              Client Application              │
               │            (Next.js 14 / REST API)           │
               └──────────────────────┬───────────────────────┘
                                      │
                     Bearer JWT (Auth0) + Tenant Context
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                             FastAPI Application                            │
│                                                                            │
│  [TenantMiddleware]  ──► Sets ContextVar & PostgreSQL RLS session vars     │
│  [AuthMiddleware]    ──► Validates JWT & enforces RBAC (Admin, Recruiter)  │
│                                                                            │
│  Routers:                                                                  │
│  ├── /v1/tenants      (Tenant management & settings)                       │
│  ├── /v1/users        (User provisioning & invitations)                    │
│  ├── /v1/jobs         (Job requisition CRUD & pipeline mapping)            │
│  ├── /v1/pipeline     (Stage workflows & automation triggers)              │
│  ├── /v1/resumes      (Multipart upload, pre-signed URLs, polling)         │
│  └── /v1/candidates   (Parsed profiles, blind screening, GDPR deletion)    │
└──────────────────────┬───────────────────────────────┬─────────────────────┘
                       │                               │
       Async Tasks     ▼                               ▼    Relational DB
    ┌──────────────────────┐               ┌────────────────────────────────┐
    │    Celery Workers    │               │         PostgreSQL 16          │
    │  (Redis Task Broker) │               │   (Row-Level Security Enabled) │
    └──────────┬───────────┘               └────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              Core NLP Engine                               │
│                                                                            │
│  • Extractor:   PDFMiner.six (multi-column) & python-docx                  │
│  • Taxonomy:    100+ normalized skills with alias & word-boundary regex    │
│  • Parser:      Contact info, tenure calculator, degree normalizer         │
│  • Anti-Bias:   PII scrubber for demographic-blind evaluations             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Features

### 🏢 Multi-Tenancy & Security
- **Strict Data Isolation:** Dual-layer tenant isolation via PostgreSQL Row-Level Security (RLS) policies and application-level `tenant_id` query scoping.
- **Enterprise RBAC:** Granular role-based access control supporting `ADMIN`, `RECRUITER`, `HIRING_MANAGER`, and `INTERVIEWER`.
- **Tenant Context Resolution:** Automatic tenant discovery from JWT claims (`org_id` / `tenant_id`) and fallback `X-Tenant-ID` headers.

### 📄 Document Ingestion & NLP Resume Parsing
- **Format Support:** Extracts text from multi-column PDF resumes via `pdfminer.six` and DOCX documents via `python-docx`.
- **Skills Normalization:** Canonical taxonomy covering 100+ tech skills across 9 categories with automated alias resolution (e.g., `k8s` $\rightarrow$ `Kubernetes`, `react.js` $\rightarrow$ `React`, `postgres` $\rightarrow$ `PostgreSQL`).
- **Tenure & Work History:** Regex-based date extraction, duration estimation in months, current role/company detection.
- **Education Classification:** Normalizes academic credentials into canonical degree levels (`DOCTORATE`, `MASTERS`, `BACHELORS`, `ASSOCIATES`, `HIGHSCHOOL`).
- **Anti-Bias Blind Screening:** Redacts candidate names, emails, phone numbers, and graduation years with `?blind=true` to eliminate demographic bias during initial reviews.
- **GDPR Compliance:** Complete candidate data lifecycle management with cascading deletion ("Right to be Forgotten").

### 📦 Hybrid Object Storage
- Seamless abstraction supporting **AWS S3** in production and local filesystem storage (`./uploads`) in local development.
- Secure direct client-side upload support via S3 pre-signed URLs.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.12+ / FastAPI, Pydantic v2
- **Database ORM:** SQLAlchemy 2.0 (Async) + `asyncpg` connection pooling
- **Database:** PostgreSQL 16 (Row-Level Security)
- **Background Tasks:** Celery + Redis 7
- **Vector DB:** Qdrant (Scaffolded for semantic matching)
- **Document Processing:** `pdfminer.six`, `python-docx`
- **Testing:** Pytest, `pytest-asyncio`, `httpx` (In-memory SQLite & PostgreSQL test harness)

---

## ⚡ Quickstart Guide

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.12+

### 2. Start Infrastructure
Run PostgreSQL, Redis, and Qdrant locally:
```bash
docker compose up -d
```

### 3. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
```

### 4. Run the API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive API documentation will be available at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 5. Run the Background Worker
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

---

## 🧪 Testing & Code Quality

Run the test suite with coverage report:
```bash
cd backend
pytest tests/ -v
```

**Current Test Results:**
- **32 / 32 tests passing** (100% pass rate)
- **87% overall backend coverage** (97% parser coverage, 94% taxonomy coverage)

---

## 🗺️ Project Roadmap

- [x] **Phase 1: Foundation Scaffold** (FastAPI, SQLAlchemy 2.0 Async, PostgreSQL RLS, Auth0 JWT RBAC, Docker Compose, Pytest Isolation Suite)
- [x] **Phase 2: Ingestion & Core NLP Parser** (S3/Local storage, PDFMiner + python-docx, Canonical Skills Taxonomy, Tenure/Degree extraction, PII Blind Screening, Celery async tasks)
- [ ] **Phase 3: Vector Embeddings & Intelligent Semantic Matching** (Qdrant vector collection, dense embeddings, composite scoring formula)
- [ ] **Phase 4: Customizable Pipeline Engine & Automation Triggers** (FSM state transitions, webhook/email triggers, scorecard reviews)
- [ ] **Phase 5: Hardening, Analytics Dashboard, and Enterprise Compliance**

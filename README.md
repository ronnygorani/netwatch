# NetWatch — Network Observability Platform

A multi-module network monitoring platform built as a portfolio project targeting
DevOps, Platform, and Solution Engineering roles.

Demonstrates: containerization, CI/CD pipelines, REST API design, C++ systems
programming, Python automation, and Kubernetes production deployment.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        NetWatch Platform                          │
│                                                                  │
│  ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐  │
│  │  C++ Probe   │   │  C++ Packet    │   │ Python Network   │  │
│  │  Engine      │   │  Analyzer      │   │ Automator        │  │
│  │  (Phase 2)   │   │  (Phase 3)     │   │ (Phase 4)        │  │
│  │              │   │                │   │                  │  │
│  │ ICMP + TCP   │   │ libpcap        │   │ Netmiko SSH      │  │
│  │ raw sockets  │   │ packet decode  │   │ compliance audit │  │
│  └──────┬───────┘   └───────┬────────┘   └────────┬─────────┘  │
│         │                   │                     │             │
│         └───────────────────┼─────────────────────┘             │
│                             │  HTTP                             │
│                             ▼                                   │
│                  ┌──────────────────────┐                       │
│                  │   FastAPI REST API   │                       │
│                  │   (Phase 1+)         │                       │
│                  │                      │                       │
│                  │  GET  /health        │                       │
│                  │  POST /metrics       │  ← Phase 2            │
│                  │  POST /packets       │  ← Phase 3            │
│                  │  GET  /devices       │  ← Phase 4            │
│                  └──────────┬───────────┘                       │
│                             │                                   │
│                  ┌──────────────────────┐                       │
│                  │     PostgreSQL       │                       │
│                  └──────────────────────┘                       │
└──────────────────────────────────────────────────────────────────┘
```

**Key design principle:** The API is the only integration point. Modules never
talk to each other directly. This means you can rewrite any module independently.

---

## Build Phases

| Phase | Focus                              | Status        |
|-------|------------------------------------|---------------|
| 1     | Foundation: FastAPI, Docker, CI/CD | ✅ Complete   |
| 2     | C++ ICMP/TCP probe engine          | Planned       |
| 3     | C++ libpcap packet analyzer        | Planned       |
| 4     | Python Netmiko network automator   | Planned       |
| 5     | AWS EKS + Terraform + Kubernetes   | Planned       |
| 6     | Observability + Portfolio polish   | Planned       |

---

## Tech Stack

| Layer                    | Technology                                |
|--------------------------|-------------------------------------------|
| API Framework            | Python / FastAPI + Uvicorn                |
| Database                 | PostgreSQL 16 (SQLAlchemy ORM)            |
| Probe Engine             | C++ / raw sockets / ICMP                  |
| Packet Capture           | C++ / libpcap (same library as Wireshark) |
| Network Automation       | Python / Netmiko (SSH to network devices) |
| Containerization         | Docker (multi-stage builds)               |
| Local Dev                | Docker Compose                            |
| Production Orchestration | Kubernetes on AWS EKS                     |
| Infrastructure as Code   | Terraform                                 |
| Image Registry           | AWS ECR                                   |
| CI/CD                    | GitHub Actions                            |

---

## Quick Start (Phase 1)

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Clone the repository
git clone <repo-url>
cd netwatch

# 2. Create your environment file
cp .env.example .env
# The defaults in .env.example work for local development — no edits needed

# 3. Start the API and database
docker compose up --build

# 4. Verify the API is healthy
curl http://localhost:8000/health

# 5. Open the live dashboard
start dashboard/index.html

# 6. Explore the interactive API docs
# Open in browser: http://localhost:8000/docs

# 7. Stop everything
docker compose down

# 8. Stop and wipe the database volume
docker compose down -v
```

**Expected response from /health:**
```json
{
    "status": "healthy",
    "environment": "development",
    "uptime_seconds": 3.14,
    "database": "connected",
    "python_version": "3.12.x"
}
```

---

## Repository Structure

```
netwatch/
├── .github/
│   └── workflows/
│       └── ci.yml             # CI: lint → test → build on every push
│
├── api/                       # FastAPI service (all phases)
│   ├── app/
│   │   ├── config.py          # Centralized config from env vars
│   │   ├── database.py        # SQLAlchemy engine, sessions, health check
│   │   ├── main.py            # App factory, router registration
│   │   └── routers/
│   │       └── health.py      # GET /health endpoint
│   ├── tests/
│   │   └── test_health.py     # Pytest tests (3 tests, DB mocked)
│   ├── Dockerfile             # Multi-stage build, non-root user
│   └── requirements.txt       # Pinned Python dependencies
│
├── probe-engine/              # C++ ICMP/TCP prober (Phase 2)
├── packet-analyzer/           # C++ libpcap analyzer (Phase 3)
├── network-automator/         # Python Netmiko (Phase 4)
│
├── infra/
│   ├── terraform/             # AWS infrastructure as code (Phase 5)
│   └── k8s/                   # Kubernetes manifests (Phase 5)
│
├── dashboard/
│   └── index.html             # Live HTML/JS dashboard (no framework)
│
├── scripts/
│   └── wait-for-db.sh         # Startup readiness gate for Docker Compose
│
├── docker-compose.yml         # Local dev: api + db, shared network
├── .env.example               # Environment variable template
└── .gitignore                 # Excludes secrets, bytecode, build artifacts
```

---

## CI/CD Pipeline

Every `git push` to `main` (and every pull request) triggers:

```
Push to GitHub
      │
      ▼
[1] Lint (Ruff)        ← fails fast on style errors
      │
      ▼
[2] Test (Pytest)      ← 3 tests, real PostgreSQL service container
      │
      ▼
[3] Build (Docker)     ← verifies the image is buildable
                         Phase 5: will push to ECR and deploy to EKS
```

Results are visible in the **Actions** tab on GitHub.

---

## Talking Points (Interview Reference)

**Why is the API the only integration point?**
Loose coupling. Each module only knows one contract: the HTTP API. You can
rewrite the probe engine in Go or swap PostgreSQL for TimescaleDB without
touching other modules.

**Why Docker multi-stage builds?**
The builder stage needs `gcc` to compile psycopg2. The runtime image doesn't.
Multi-stage discards the compiler — smaller image, smaller attack surface.

**Why pin Python package versions?**
Reproducibility. `fastapi==0.115.6` today and six months from now produce
identical environments. Unpinned packages can silently pull breaking changes.

**Why does /health return 503 when the DB is down?**
Kubernetes readiness probes act on HTTP status codes. A 503 causes K8s to
remove the pod from the load balancer rotation. A health endpoint that always
returns 200 is worse than useless — it hides real failures.

**Why `pool_pre_ping=True`?**
After a DB restart, connections in SQLAlchemy's pool become stale. Pre-ping
sends `SELECT 1` before reusing a connection — transparent recovery with zero
errors to end users.

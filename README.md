# NetAuto — Network Automation Platform

A centralized network automation platform for multi-site Cisco environments, built as a portfolio project targeting DevOps, Platform, and Solution Engineering roles.

## What it does

NetAuto gives network teams a single platform to monitor device health, manage configurations, and control changes across every site — with a full audit trail for every action.

- **Device Inventory** — centralised database of all switches, routers, and firewalls across all sites
- **Health Poller** — SSHes into each device on a schedule via Netmiko, collects CPU, memory, and uptime, stores time-series metrics
- **Config Manager** *(Phase 3)* — pulls running configs, compares against Jinja2 baseline templates, flags any drift
- **Change Workflow** *(Phase 4)* — network admins submit change requests that open a GitHub PR; a senior engineer approves; merge triggers automatic deployment to the device with a full audit log

All modules communicate exclusively through a single **FastAPI REST API** backed by **PostgreSQL**, surfaced via a live HTML dashboard.

## Architecture

```
                        ┌─────────────────────────────┐
  Netmiko Poller  ──────►                             │
                        │   FastAPI REST API          ├──► PostgreSQL
  Config Manager  ──────►   (single integration       │
                        │    point for all modules)   │
  Change Workflow ──────►                             │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                               Live Dashboard
                             (polls API every 5s)
```

Change workflow specifically:

```
  Network admin                GitHub                  Device
  submits request  ──► PR created with config diff ──► approved & merged
                                                           │
                                               GitHub Actions pushes
                                               change via Netmiko
                                                           │
                                               Result posted to audit log
```

## Stack

| Layer | Technology |
|---|---|
| Network automation | Python, Netmiko |
| API | Python, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes on AWS EKS |
| Infrastructure as Code | Terraform |
| CI/CD | GitHub Actions |
| Dashboard | Vanilla HTML/JS |

## Project structure

```
netwatch/
├── api/                    # FastAPI application
│   ├── app/
│   │   ├── main.py         # App factory, lifespan, router registration
│   │   ├── config.py       # Environment variable config (pydantic-settings)
│   │   ├── database.py     # SQLAlchemy engine, session factory
│   │   ├── models/         # ORM table definitions
│   │   ├── schemas/        # Pydantic request/response validation
│   │   └── routers/        # One file per resource (/health, /devices, /metrics)
│   └── tests/              # Pytest suite (SQLite in-memory, no Postgres needed)
├── poller/                 # Netmiko polling service (separate container)
├── dashboard/              # Single HTML file, polls API every 5s
├── infra/
│   ├── k8s/                # Kubernetes manifests (Phase 5)
│   └── terraform/          # AWS infrastructure as code (Phase 5)
├── docker-compose.yml      # Local dev: api + poller + postgres
└── .github/workflows/      # CI/CD pipeline
```

## Getting started

```bash
# Clone
git clone https://github.com/ronnygorani/netwatch.git
cd netwatch

# Configure environment
cp .env.example .env
# Edit .env with your SSH credentials and Postgres password

# Run
docker compose up --build

# API is now live at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | API and database status |
| `GET` | `/devices` | List all devices (filter by `?site=`) |
| `POST` | `/devices` | Add a device to the inventory |
| `PATCH` | `/devices/{id}` | Update a device |
| `DELETE` | `/devices/{id}` | Remove a device |
| `POST` | `/metrics` | Ingest a metric snapshot (used by poller) |
| `GET` | `/metrics/latest` | Latest metric for every device |
| `GET` | `/devices/{id}/metrics` | Full metric history for one device |
| `GET` | `/docs` | Auto-generated interactive API docs |

## Build phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | FastAPI `/health`, PostgreSQL, Dockerfile, Docker Compose, GitHub Actions CI | ✅ Complete |
| 2 | Device inventory API, Netmiko poller, live dashboard, 16 passing tests | ✅ Complete |
| 3 | Config manager — pull running configs, Jinja2 baseline templates, drift detection | 🔲 In progress |
| 4 | Change workflow — GitHub PR approval, auto-deploy via Actions, audit log | 🔲 Planned |
| 5 | Kubernetes manifests, Terraform AWS (EKS, ECR, VPC), GitHub Actions deploy | 🔲 Planned |

## Design principles

- **API is the single integration point** — modules never talk to each other directly; every interaction goes through the REST API
- **Secrets never in code** — all credentials via environment variables; K8s Secrets in production
- **Every change is auditable** — the GitHub PR approval workflow means every config push to a device has a reviewer, a timestamp, and a diff
- **Health endpoints on every service** — Kubernetes liveness and readiness probes depend on `/health` returning the correct status code
- **Tests run without infrastructure** — the full test suite uses SQLite in-memory; no Postgres, no SSH, no external dependencies

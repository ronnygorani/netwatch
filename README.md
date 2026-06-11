# NetWatch — Network Automation Platform

A centralized network automation platform for multi-site Cisco environments, built as a portfolio project targeting DevOps, Platform, and Solution Engineering roles.

## What it does

NetWatch gives network teams a single platform to monitor device health, manage configurations, and control changes across every site — with a full audit trail for every action.

- **Device Inventory** — centralised database of all switches, routers, and firewalls across all sites
- **Health Poller** — SSHes into each device on a schedule via Netmiko, collects CPU, memory, and uptime, stores time-series metrics
- **Config Manager** *(Phase 3)* — pulls running configs, compares against Jinja2 baseline templates, flags any drift
- **Change Workflow** *(Phase 4)* — network admins submit change requests that open a GitHub PR; a senior engineer approves; merge triggers automatic deployment to the device with a full audit log

All modules communicate exclusively through a single FastAPI REST API backed by PostgreSQL, surfaced via a live HTML dashboard.

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

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | API and database status |
| `GET` | `/devices` | List all devices (filter by `?site=`) |
| `POST` | `/devices` | Add a device to the inventory |
| `PATCH` | `/devices/{id}` | Update a device |
| `DELETE` | `/devices/{id}` | Remove a device |
| `POST` | `/metrics` | Ingest a metric snapshot (used by poller) |
| `GET` | `/metrics/latest` | Latest metric for every device |
| `GET` | `/devices/{id}/metrics` | Full metric history for one device |
| `GET` | `/docs` | Auto-generated interactive API docs |

## Getting Started

```bash
git clone https://github.com/ronnygorani/netwatch.git
cd netwatch

cp .env.example .env
# fill in your SSH credentials and Postgres password

docker compose up --build
```

API live at `localhost:8000` — interactive docs at `localhost:8000/docs`

## Build Phases

| Phase | Scope | Status |
|---|---|---|
| 1 | FastAPI `/health`, PostgreSQL, Dockerfile, Docker Compose, GitHub Actions CI | ✅ |
| 2 | Device inventory API, Netmiko poller, live dashboard, 16 passing tests | ✅ |
| 3 | Config manager — pull running configs, Jinja2 baseline templates, drift detection | 🔲 |
| 4 | Change workflow — GitHub PR approval, auto-deploy via Actions, audit log | 🔲 |
| 5 | Kubernetes manifests, Terraform AWS (EKS, ECR, VPC), GitHub Actions deploy | 🔲 |

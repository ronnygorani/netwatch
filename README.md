# NetWatch — Network Automation Platform

A centralized network automation platform for multi-site Cisco environments, built as a portfolio project targeting DevOps, Platform, and Solution Engineering roles.

## What it does

NetWatch gives network teams a single platform to monitor device health, manage configurations, and control changes across every site — with a full audit trail for every action.

- **Device Inventory** — centralised database of all switches, routers, and firewalls across all sites
- **Health Poller** — SSHes into each device on a schedule via Netmiko, collects CPU, memory, and uptime, stores time-series metrics
- **Nautobot Source of Truth** *(Phase 3)* — stand up Nautobot as the single SoT; seed sites and devices; FastAPI reads inventory via `pynautobot`; dashboard shows live SoT data
- **Ansible Automation** *(Phase 4)* — Ansible pulls dynamic inventory from Nautobot, runs backup and fact-gathering playbooks; FastAPI triggers runs via `ansible-runner` with job-status tracking

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
| 1 | FastAPI `/health`, PostgreSQL, Dockerfile, Docker Compose, GitHub Actions CI | Completed |
| 2 | Device inventory API, Netmiko poller, live dashboard, 16 passing tests | Completed |
| 3 | Nautobot Source of Truth — stand up Nautobot + Redis, seed inventory, FastAPI reads via `pynautobot` | Planned |
| 4 | Ansible Automation — dynamic inventory from Nautobot, backup/fact playbooks, `ansible-runner` job API | Planned |
| 5 | Kubernetes manifests, Terraform AWS (EKS, ECR, VPC), GitHub Actions deploy | Planned |

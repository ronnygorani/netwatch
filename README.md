# NetAuto

A network automation platform I'm building to centralize config management and health monitoring across multi-site Cisco environments.

Network admins submit config changes through the platform. Changes go through a review and approval flow before anything touches a device — every push is tracked, reviewed, and logged.

## Stack

Python, FastAPI, PostgreSQL, Netmiko, Docker, Kubernetes, Terraform, AWS EKS, GitHub Actions

## Modules

**Poller** — SSHes into devices on a schedule, collects CPU/memory/uptime, stores time-series metrics

**Config Manager** *(in progress)* — pulls running configs, compares against baseline templates, flags drift

**Change Workflow** *(planned)* — submit a change → GitHub PR for review → approve → auto-deploy via Actions → audit log

## Running locally

```bash
cp .env.example .env
# fill in your SSH credentials and Postgres password

docker compose up --build
```

API at `localhost:8000` — interactive docs at `localhost:8000/docs`

## Status

| Phase | | Status |
|---|---|---|
| 1 | FastAPI, PostgreSQL, Docker, CI/CD | ✅ |
| 2 | Device inventory, Netmiko poller, live dashboard | ✅ |
| 3 | Config manager, drift detection | 🔲 |
| 4 | Change workflow, GitHub PR approval, audit log | 🔲 |
| 5 | Kubernetes, Terraform, AWS EKS | 🔲 |

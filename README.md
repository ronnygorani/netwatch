# NetWatch

Network monitoring and automation platform for multi-site, multi-vendor networks.

[![CI](https://github.com/ronnygorani/netwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/ronnygorani/netwatch/actions/workflows/ci.yml)

NetWatch keeps a central inventory of network devices, polls them over SSH on a
schedule, and serves health data through a single versioned REST API with a live
dashboard on top. It ships with a reproducible three-switch Arista cEOS lab so the
whole platform can be run and demonstrated on one machine.

## Features

- Device inventory with full CRUD over a versioned REST API (`/v1`)
- Scheduled SSH health polling (CPU, memory, uptime) with a bounded concurrent
  worker pool; one slow or dead device never stalls a cycle
- Scoped API key authentication for services (keys stored as SHA-256 hashes only)
- Collector heartbeat with staleness detection: a dead poller shows up red on the
  dashboard instead of leaving stale data that looks healthy
- Pagination, per-key rate limiting, and automatic metric retention
- Database schema managed entirely by Alembic migrations
- Single-file dashboard with no build step
- Lab topology defined as code with ContainerLab and Arista cEOS

## Architecture

Three services run under Docker Compose: a PostgreSQL database, the FastAPI
control plane, and the SSH poller. Every component communicates exclusively
through the API; nothing else touches the database. Configuration enters only
through environment variables, so the same images run in development, CI, and
production.

## Tech stack

Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16, Netmiko,
Docker Compose, ContainerLab with Arista cEOS, GitHub Actions.

## Quick start

Requires Docker with the compose plugin.

```bash
git clone https://github.com/ronnygorani/netwatch.git
cd netwatch
cp .env.example .env        # set a real POSTGRES_PASSWORD

docker compose up -d --build

# Mint a key for the poller, paste it into .env as NETWATCH_API_KEY, then:
docker compose exec api python -m app.create_api_key poller "metrics:write"
docker compose up -d poller
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`). Open
`dashboard/index.html` in a browser for the live dashboard.

A three-switch Arista cEOS lab topology for ContainerLab is included under
`lab/` for local development against real network operating systems.

## API overview

| Method | Endpoint                    | Description                    | Auth           |
|--------|-----------------------------|--------------------------------|----------------|
| GET    | `/health`                   | Service and database status    | none           |
| GET    | `/v1/devices`               | List devices (paginated)       | none           |
| POST   | `/v1/devices`               | Add a device                   | `devices:write`|
| PATCH  | `/v1/devices/{id}`          | Update a device                | `devices:write`|
| DELETE | `/v1/devices/{id}`          | Remove a device                | `devices:write`|
| GET    | `/v1/devices/{id}/metrics`  | Metric history (paginated)     | none           |
| POST   | `/v1/metrics`               | Ingest a metric                | `metrics:write`|
| GET    | `/v1/metrics/latest`        | Latest metric per device       | none           |
| POST   | `/v1/poller/heartbeat`      | Collector liveness report      | `metrics:write`|
| GET    | `/v1/poller/status`         | Collector status               | none           |

Authenticated endpoints take an `X-API-Key` header. List endpoints return
`{items, total, limit, offset}` envelopes. Full request and response schemas are
in the interactive docs at `/docs`.

## Development

```bash
ruff check api/ poller/ && ruff format api/ poller/ --check   # lint
cd api && pytest tests/ -q                                    # API tests (SQLite)
cd poller && pytest tests/ -q                                 # parser and runner tests
```

Set `TEST_DATABASE_URL` to run the API tests against PostgreSQL; CI does this on
every push, along with an Alembic upgrade/downgrade/upgrade cycle and a Docker
image build.

## Roadmap

| Phase | Scope                                                              | Status      |
|-------|--------------------------------------------------------------------|-------------|
| 1     | API foundation, PostgreSQL, Docker, CI                             | Done        |
| 2     | Device inventory, SSH poller, dashboard                            | Done        |
| 3     | Auth, migrations, concurrency, versioning, rate limits, retention  | Done        |
| 4     | ContainerLab cEOS lab, multi-vendor polling via NAPALM             | Done        |
| 5     | Nautobot as the source of truth                                    | Done        |
| 6     | Ansible execution and a change workflow with approvals             | In progress |
| 7     | Config drift detection, streaming telemetry                        | Planned     |
| 8     | Kubernetes, Terraform, AWS deployment                              | Planned     |

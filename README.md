# NetWatch — Network Observability Platform

A multi-module network monitoring platform built as a portfolio project targeting DevOps, Platform, and Solution Engineering roles.

## What it does

NetWatch collects, analyzes, and visualizes network health data from three independent engines:

- **Probe Engine** (C++) — ICMP ping and TCP port checks; tracks host uptime, latency, and packet loss using raw sockets
- **Packet Analyzer** (C++) — live traffic capture via libpcap; decodes packet headers, tracks top talkers, and flags anomalies
- **Network Automator** (Python) — SSHs into network devices via Netmiko, audits configs against compliance rules, and auto-remediates violations

All three feed into a single **FastAPI REST API** backed by **PostgreSQL**, with a live HTML dashboard as the front end.

## Stack

| Layer | Technology |
|---|---|
| Probe engine | C++, raw sockets, ICMP |
| Packet capture | C++, libpcap |
| Network automation | Python, Netmiko |
| API | Python, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Containers | Docker, Docker Compose |
| Orchestration | Kubernetes on AWS EKS |
| Infrastructure | Terraform |
| CI/CD | GitHub Actions |

## Architecture

All modules communicate exclusively through the API — they never talk to each other directly. This keeps each component independently deployable and replaceable.

```
  Probe Engine  ──┐
 Packet Analyzer ─┼──▶  FastAPI  ──▶  PostgreSQL
Network Automator ┘
```

## Status

Active development. See open pull requests and branches for in-progress work.

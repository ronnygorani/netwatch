#!/usr/bin/env bash
# One-command lab bring-up. Run inside WSL2 Ubuntu:
#   wsl -d Ubuntu -u root -- bash /mnt/c/Users/ronny/Projects/NetWatch/lab/up.sh
#
# WSL shuts its VM down when idle (vmIdleTimeout is unreliable), which kills
# the ContainerLab switches; compose services restart themselves but the lab
# does not. This restores everything to a known-good state (FM-C9).
set -e
cd "$(dirname "$0")/.."

echo "== stack =="
docker compose up -d
until curl -s -m 3 http://localhost:8000/health | grep -q healthy; do sleep 3; done
echo "api healthy"

echo "== lab switches =="
running=$(docker ps --filter name=clab-netwatch --filter status=running -q | wc -l)
if [ "$running" -lt 3 ]; then
  # Clean redeploy: cEOS can Exit(255) on a stale --reconfigure under WSL2,
  # so tear down any partial state first, then deploy fresh.
  containerlab destroy -t lab/topology.clab.yml >/dev/null 2>&1 || true
  containerlab deploy -t lab/topology.clab.yml >/dev/null 2>&1
fi
echo "switches deployed"

echo "== bridge poller and worker to the lab network =="
docker network connect netwatch-lab netwatch-poller 2>/dev/null || true
docker network connect netwatch-lab netwatch-worker 2>/dev/null || true

docker ps --format '{{.Names}}: {{.Status}}' | sort
echo "lab up. Switches need ~1-2 min to finish booting EOS."

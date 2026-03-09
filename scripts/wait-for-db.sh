#!/usr/bin/env bash
# Block until a TCP port accepts connections, then exec the given command.
# Usage: wait-for-db.sh <host> <port> -- <command>
#
# depends_on: service_healthy waits for pg_isready, but there's a brief
# window where PostgreSQL is initializing its listener. This script
# eliminates that race by testing the actual TCP connection.

set -euo pipefail

HOST="${1:?Usage: wait-for-db.sh <host> <port> -- <cmd>}"
PORT="${2:?Usage: wait-for-db.sh <host> <port> -- <cmd>}"
shift 2

if [[ "${1:-}" == "--" ]]; then
    shift
fi

echo "[wait-for-db] Waiting for ${HOST}:${PORT}..."

until nc -z "${HOST}" "${PORT}" 2>/dev/null; do
    echo "[wait-for-db] ${HOST}:${PORT} not ready — retrying in 2s"
    sleep 2
done

echo "[wait-for-db] ${HOST}:${PORT} is ready. Starting: $*"

# exec replaces this shell with the target process, making it PID 1.
# PID 1 receives SIGTERM from Docker/Kubernetes during graceful shutdown.
exec "$@"

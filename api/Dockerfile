# Multi-stage build: builder installs dependencies, runtime copies only
# the compiled packages — no build tools (gcc, etc.) in the final image.

# ── Stage 1: install dependencies ────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy requirements first so Docker's layer cache skips pip install
# on rebuilds where only application code changed.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: lean runtime image ───────────────────────────────
FROM python:3.12-slim AS runtime

# Run as a non-root user — security best practice for container workloads.
RUN groupadd --gid 1001 netwatch && \
    useradd --uid 1001 --gid netwatch --no-create-home netwatch

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ ./app/
# Migrations ship with the image so `alembic upgrade head` can run as a
# deploy step from the same artifact that serves traffic.
COPY alembic.ini ./
COPY alembic/ ./alembic/

USER netwatch

EXPOSE 8000

# Use Python's built-in urllib — no curl needed in the slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# --host 0.0.0.0 is required inside a container; 127.0.0.1 would not
# accept connections routed in from outside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

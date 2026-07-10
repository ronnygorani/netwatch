# Multi-stage: build deps in one stage, ship only installed packages.
FROM python:3.12-slim AS builder

WORKDIR /build

# Requirements first so the pip layer caches across code-only rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim AS runtime

RUN groupadd --gid 1001 netwatch && \
    useradd --uid 1001 --gid netwatch --no-create-home netwatch

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ ./app/
# Migrations ship in the image so `alembic upgrade head` runs from the same artifact.
COPY alembic.ini ./
COPY alembic/ ./alembic/

USER netwatch

EXPOSE 8000

# urllib instead of curl: slim image has no curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

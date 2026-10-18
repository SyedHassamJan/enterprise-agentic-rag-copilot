# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Multi-stage build
#   builder : installs Python dependencies into an isolated virtualenv
#   runtime : copies only that virtualenv + app code -> smaller, cleaner image
# ---------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Copy only requirements first so this layer is cached until dependencies change.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="employee-support-copilot" \
      org.opencontainers.image.description="Multi-department agentic RAG copilot (IT + HR)" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8080 \
    AUDIT_DB_PATH=/app/var/audit.db \
    UPLOAD_DIR=/app/var/uploads

# Run as an unprivileged user, never as root.
RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app templates ./templates
COPY --chown=app:app static ./static
COPY --chown=app:app data/sample_kb ./data/sample_kb
COPY --chown=app:app scripts/healthcheck.py ./scripts/healthcheck.py
COPY --chown=app:app ingest_sample_kb.py run.py ./

# Writable state (audit log, uploaded files) lives in one directory -> mount it as a volume.
RUN mkdir -p /app/var && chown app:app /app/var
VOLUME ["/app/var"]

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "scripts/healthcheck.py"]

# exec -> uvicorn becomes PID 1 and receives SIGTERM directly for graceful shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]

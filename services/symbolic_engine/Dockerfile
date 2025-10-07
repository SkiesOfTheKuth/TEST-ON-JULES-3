# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /workspace

COPY requirements.txt ./

RUN pip wheel --no-cache-dir --wheel-dir /workspace/wheels -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /workspace/requirements.txt ./
COPY --from=builder /workspace/wheels /wheels
RUN pip install --no-cache-dir /wheels/*

COPY app ./app
COPY scripts ./scripts
COPY pyproject.toml ./
COPY README.md ./

RUN useradd --create-home symbolic && \
    chown -R symbolic:symbolic /app && \
    chmod +x /app/scripts/start.sh

USER symbolic

EXPOSE 8082

ENTRYPOINT ["/app/scripts/start.sh"]

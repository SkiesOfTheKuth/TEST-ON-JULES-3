# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    && rm -rf /var/lib/apt/lists/*
COPY services/symbolic_engine/pyproject.toml /tmp/symbolic/
COPY services/symbolic_engine/README.md /tmp/symbolic/
COPY services/symbolic_engine/app /tmp/symbolic/app
RUN pip install --upgrade pip && \
    pip install --prefix=/install /tmp/symbolic

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY services/symbolic_engine/app /app/app
ENV PYTHONPATH="/app"
ENV SYMBOLIC_PORT=8100
EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

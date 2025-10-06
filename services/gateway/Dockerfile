# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY services/gateway/pyproject.toml /tmp/gateway/
COPY services/gateway/README.md /tmp/gateway/
COPY services/gateway/app /tmp/gateway/app
COPY services/gateway/alembic /tmp/gateway/alembic
COPY services/gateway/alembic.ini /tmp/gateway/alembic.ini
COPY services/protos /tmp/gateway/services/protos
COPY services/common /tmp/gateway/services/common
COPY calculator_grpc /tmp/gateway/calculator_grpc
COPY libs /tmp/libs
RUN mkdir -p /libs && cp -r /tmp/libs/* /libs/
RUN pip install --upgrade pip && \
    pip install --prefix=/install -e /libs/calculator_logic && \
    pip install --prefix=/install -e /libs/calculator_core && \
    pip install --prefix=/install -e /tmp/gateway

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY services/gateway/app /app/app
COPY services/gateway/alembic /app/alembic
COPY services/gateway/alembic.ini /app/alembic.ini
COPY services/common /app/services/common
COPY services/protos /app/services/protos
COPY calculator_grpc /app/calculator_grpc
ENV PYTHONPATH="/app"
ENV GATEWAY_HOST=0.0.0.0
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

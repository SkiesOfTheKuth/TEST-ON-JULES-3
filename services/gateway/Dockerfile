# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY services/gateway/pyproject.toml /tmp/gateway/
COPY libs /tmp/libs
RUN pip install --upgrade pip && \
    pip install --prefix=/install -e /tmp/libs/calculator_logic && \
    pip install --prefix=/install -e /tmp/libs/calculator_core && \
    pip install --prefix=/install -e /tmp/gateway

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY services/gateway/app /app/app
ENV GATEWAY_HOST=0.0.0.0
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

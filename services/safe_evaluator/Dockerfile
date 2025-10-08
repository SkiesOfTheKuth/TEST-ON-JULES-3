# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY services/safe_evaluator/pyproject.toml /tmp/evaluator/
COPY services/safe_evaluator/README.md /tmp/evaluator/
COPY services/safe_evaluator/app /tmp/evaluator/app
COPY services/protos /tmp/evaluator/services/protos
COPY services/common /tmp/evaluator/services/common
COPY calculator_grpc /tmp/evaluator/calculator_grpc
COPY libs /tmp/libs
RUN mkdir -p /libs && cp -r /tmp/libs/* /libs/
RUN pip install --upgrade pip && \
    pip install --prefix=/install -e /libs/calculator_logic && \
    pip install --prefix=/install -e /libs/calculator_core && \
    pip install --prefix=/install -e /tmp/evaluator

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY services/safe_evaluator/app /app/app
COPY services/protos /app/services/protos
COPY services/common /app/services/common
COPY calculator_grpc /app/calculator_grpc
ENV PYTHONPATH="/app"
ENV EVALUATOR_HOST=0.0.0.0
EXPOSE 50051
CMD ["python", "-m", "app.server"]

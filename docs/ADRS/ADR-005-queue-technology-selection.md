# ADR-005 – Queue Technology Selection

- **Status:** Accepted
- **Date:** 2024-06-01

## Context

The Phase 2 roadmap extends the calculator platform with asynchronous job orchestration. We must choose a queue and worker technology that fits the Python-first stack, runs in constrained environments (Docker Compose or Kubernetes), integrates with existing Redis infrastructure, and exposes first-class observability (Prometheus + OpenTelemetry). Jobs require retries, priority routing, WebSocket notifications, and eventual migration paths for higher durability.

## Options

1. **Celery + Redis** – Battle-tested Python task queue with rich retry semantics, ETA scheduling, and a vibrant ecosystem. Can run on Redis or RabbitMQ.
2. **RQ (Redis Queue)** – Lightweight Redis-backed queue designed for simple background jobs.
3. **Arq** – Asyncio-native Redis queue with coroutine workers and minimal configuration.
4. **RabbitMQ + custom consumers** – Use AMQP directly with bespoke worker implementation.

## Evaluation

| Criteria | Celery + Redis | RQ | Arq | RabbitMQ + custom |
| --- | --- | --- | --- | --- |
| Reliability & retries | ✅ Mature retry/backoff controls, acks-late, ETA scheduling | ⚠️ Basic retry logic; no native backoff | ⚠️ Retries available but fewer tuning knobs | ✅ Durable queues but requires bespoke retry logic |
| Visibility & metrics | ✅ Built-in Prometheus exporters and signals, large ecosystem | ⚠️ Limited metrics, requires custom instrumentation | ⚠️ Minimal metrics surface | ❌ Requires building metrics from scratch |
| Python ecosystem fit | ✅ First-class support, Celery workers integrate with FastAPI/async code | ✅ Simple to adopt but synchronous worker model | ✅ Async-first but smaller community | ⚠️ Non-Python control plane; more boilerplate |
| Cost & operational overhead | ✅ Reuses Redis (already deployed) | ✅ Reuses Redis | ✅ Reuses Redis | ❌ Introduces RabbitMQ cluster management |
| Scheduling & routing | ✅ Priority queues, ETA countdowns, routing keys | ⚠️ Single queue semantics; priority via multiple queues | ⚠️ Similar limitations as RQ | ✅ Rich AMQP routing but requires additional tooling |
| Observability maturity | ✅ Community exporters, OpenTelemetry hooks | ⚠️ Requires custom exporters | ⚠️ Requires hand-rolled traces | ❌ Must design instrumentation entirely |

## Decision

Adopt **Celery with Redis** for Phase 2. Celery delivers retries, priority routing, ETA scheduling, and a mature ecosystem for instrumentation. Redis is already provisioned for caching and rate limiting, enabling a lean deployment footprint. Celery's worker model integrates with both synchronous and async workloads, and the existing team is familiar with its operational model.

## Consequences

- **Pros:** Unified tooling (Celery CLI, Flower) for operations, seamless integration with Prometheus and OpenTelemetry, straightforward scaling via worker processes, and compatibility with the existing Redis stack.
- **Cons:** Redis-backed Celery queues are ephemeral; for strict durability we may need RabbitMQ or Redis persistence tuning. Workers require careful tuning of prefetch counts to avoid starvation. The Celery configuration surface is large, increasing complexity.
- **Future path:** If durability or throughput requirements grow beyond Redis, migrate Celery to RabbitMQ without rewriting tasks. Alternatively, evaluate Kafka-based workflows for streaming workloads while retaining Celery for control-plane tasks.

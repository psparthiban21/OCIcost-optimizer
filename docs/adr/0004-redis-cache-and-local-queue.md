# ADR-0004: Use Redis for Cache and Local Queue Semantics

## Status

Accepted

## Context

The dashboard needs low-latency reads for repeated summaries, and local development needs a lightweight way to decouple ingestion, analytics, and recommendation workers.

## Decision

Use Redis for:

- Cache-aside dashboard summaries.
- Short-lived recommendation and copilot context.
- Local stream or queue semantics for worker coordination.

In OCI, evaluate replacing queue semantics with OCI Queue or OCI Streaming while keeping Redis-compatible cache for hot reads.

## Consequences

Positive:

- Simple local setup.
- Fast dashboard reads.
- Supports lightweight asynchronous flow.

Negative:

- Redis streams are not the strongest durability choice for production eventing.
- Cache invalidation must be explicit after ingestion and recommendation updates.

## Follow-Up

Use OCI Queue for task queues or OCI Streaming for replay-heavy event pipelines in production.


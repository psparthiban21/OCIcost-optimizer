# ADR-0007: Build the Standalone Local App First

## Status

Accepted

## Context

The project should first be useful for local development and personal demos. Running Minikube, PostgreSQL, Redis, and multiple services too early adds operational work before the dashboard workflow, mock data model, and recommendation experience are proven.

ADR-0001 selected a Minikube-first architecture. That direction remains useful for a later deployment phase, but it is no longer the first implementation target.

## Decision

Build Phase 1 as a standalone local Python/Node-style application:

- One local backend process serves both API routes and the dashboard frontend.
- Mock OCI cost, usage, inventory, and recommendation data are deterministic.
- The frontend talks to API-shaped routes so the UI contract can survive later backend changes.
- OCI SDK, database, cache, queue, and LLM provider integrations remain behind future adapters.
- Kubernetes manifests are kept as optional deployment material, not the primary development path.

## Consequences

Positive:

- Faster local startup and iteration.
- Easier demos without cluster or cloud setup.
- Lower early complexity while the product workflow is still taking shape.
- Existing service boundaries can still be extracted later.

Negative:

- Phase 1 does not exercise distributed deployment behavior.
- Some production concerns, such as auth, retries, job workers, and persistence, remain deferred.

## Follow-Up

Improve the local dashboard and mock API until the core cost optimization workflow is clear. Then introduce real OCI adapters, persistence, and optional Minikube deployment one capability at a time.

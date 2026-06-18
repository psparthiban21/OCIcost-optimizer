# ADR-0001: Use a Minikube-First, OCI-Ready Architecture

## Status

Superseded by [ADR-0007](./0007-standalone-local-app-first.md)

## Context

The first target is a Mac laptop running Minikube. The final target is OCI-managed infrastructure. The architecture must support local development and demos without creating a throwaway design that blocks OCI migration later.

## Decision

Use Kubernetes-compatible service boundaries from the beginning:

- Frontend dashboard.
- Backend API.
- Ingestion service.
- Cost analytics engine.
- Recommendation orchestrator.
- AI agent service.
- PostgreSQL.
- Redis.

Local infrastructure will use Minikube manifests. Production infrastructure will map those boundaries to OCI services, mainly OKE, OCI Container Registry, managed database, managed cache, OCI Queue or Streaming, OCI Vault, and OCI Generative AI.

## Consequences

Positive:

- Local and production architectures stay aligned.
- Service boundaries are explicit early.
- Minikube manifests become a useful foundation for OKE.

Negative:

- More moving parts than a single local app.
- Requires discipline to avoid premature distributed complexity.

## Follow-Up

Start with simple service implementations and fixture data. Add production-grade HA only when moving to OCI.

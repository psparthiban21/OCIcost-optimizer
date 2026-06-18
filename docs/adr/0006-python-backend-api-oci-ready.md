# ADR-0006: Use Python for the Backend API Mock and OCI-Ready Service Boundary

## Status

Accepted

## Context

The backend API should be easy to run locally while preserving the service boundary needed for Minikube and later OCI deployment. The project is currently in mock-first mode, so the service must serve deterministic fixture-backed APIs before PostgreSQL, Redis, OCI SDK integrations, and LLM provider adapters are introduced.

## Decision

Use a Python backend API for the first executable service boundary.

The initial implementation will:

- Use environment-driven configuration.
- Expose JSON health and readiness endpoints for Kubernetes probes.
- Emit structured JSON logs.
- Serve the mock dashboard frontend and API from one local process during mock mode.
- Keep deterministic recommendation logic isolated from HTTP routing.
- Use an Oracle Linux container base for OCI and OKE alignment.

## Consequences

Positive:

- Easy local startup without dependency installation.
- Clear path to add OCI SDK adapters, database repositories, Redis-backed queues, and LLM provider clients.
- Kubernetes probes and container settings are present from the start.

Negative:

- The first Python server uses the standard library rather than a full production web framework.
- Later production hardening may introduce FastAPI, Gunicorn/Uvicorn, OpenTelemetry, and OCI authentication middleware.

## Follow-Up

Replace mock fixture repositories with PostgreSQL-backed repositories and split analytics, recommendation orchestration, and agent execution into their planned service boundaries.

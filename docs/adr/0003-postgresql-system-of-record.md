# ADR-0003: Use PostgreSQL as the System of Record

## Status

Accepted

## Context

The system needs durable state for normalized cost data, inventory snapshots, analytics findings, recommendations, evidence, user actions, and agent runs. This data is relational and audit-heavy.

## Decision

Use PostgreSQL as the primary state database.

Local:

- PostgreSQL StatefulSet in Minikube.

OCI:

- Managed PostgreSQL-compatible service, Autonomous Database, or enterprise-approved relational database.

## Consequences

Positive:

- Strong consistency for recommendation lifecycle and audit data.
- Mature SQL querying for dashboard APIs.
- Easy local setup.

Negative:

- Large cost datasets may require partitioning and summary tables.
- Stateful local Kubernetes requires persistent volume handling.

## Follow-Up

Partition cost and usage tables by date and tenancy once data volume grows.


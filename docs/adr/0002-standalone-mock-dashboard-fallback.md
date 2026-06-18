# ADR-0002: Keep a Standalone Mock Dashboard Fallback

## Status

Accepted

## Context

The dashboard must be presentable even if Minikube, backend APIs, OCI credentials, or LLM providers fail. The existing HTML prototype already demonstrates the target experience with deterministic browser-side mock data.

## Decision

Keep `prototypes/oci-cost-optimizer.html` as a standalone mock-mode dashboard. Future frontend work must add live API mode beside mock mode rather than deleting the mock path.

## Consequences

Positive:

- Reliable demo path.
- Useful visual baseline for frontend implementation.
- Avoids blocking presentations on local infrastructure issues.

Negative:

- Risk of divergence between mock dashboard and real app.
- Some duplicated behavior may remain in the prototype.

## Follow-Up

Document any frontend changes against both the real app and the mock fallback. Keep the mock mode deterministic.


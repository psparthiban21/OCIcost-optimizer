# ADR-0005: Separate Deterministic Analytics from AI Recommendations

## Status

Accepted

## Context

Cost optimization requires accurate savings calculations and evidence. LLMs are useful for explanation, prioritization, and natural-language assistance, but they should not invent cost numbers or make unsupported claims.

## Decision

Split the recommendation pipeline into:

- Cost analytics engine: deterministic rules, calculations, thresholds, findings, savings estimates, and evidence.
- AI agents: explanation, risk framing, implementation steps, assumptions, confidence, and user-facing recommendation language.

Agents must consume structured findings and return structured output.

## Consequences

Positive:

- Better correctness and auditability.
- Easier testing of savings calculations.
- LLM provider can be swapped behind an adapter.

Negative:

- More pipeline stages.
- Requires schema validation and evidence linking.

## Follow-Up

Add JSON schema validation for all agent outputs before recommendations are persisted.


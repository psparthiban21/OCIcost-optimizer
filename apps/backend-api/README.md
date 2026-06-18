# Backend API

Python mock backend for the OCI Cost Optimizer dashboard.

## Local Run

```bash
cd apps/backend-api
PYTHONPATH=src python3 -m oci_cost_optimizer
```

Open:

```text
http://127.0.0.1:4310
```

## Endpoints

- `GET /api/health`
- `GET /api/ready`
- `GET /api/dashboard?region=all&service=all`
- `GET /api/recommendations?region=all&service=all`
- `POST /api/copilot`

## OCI-Ready Conventions

- Environment-driven config: `HOST`, `PORT`, `APP_MODE`, `STATIC_ROOT`.
- JSON health/readiness endpoints for Kubernetes probes.
- Structured JSON logs.
- Oracle Linux container base in `Dockerfile`.
- Mock mode isolated behind API routes so OCI SDK, database, Redis, and LLM adapters can replace fixture logic later.

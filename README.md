# OCI Cost Optimizer AI Recommendation

Enterprise-grade OCI cost optimization with a Minikube-first microservice architecture, pluggable OCI data providers, and AI-assisted recommendations.

The repository currently includes a working `backend-api` service and frontend assets. The target architecture splits ingestion, analytics, recommendation orchestration, and LLM execution into independently deployable services that can run locally in Minikube before moving to OKE or another enterprise Kubernetes platform.

Architecture docs:

- [OCI Cloud Replica Architecture](docs/oci-cloud-replica-architecture.md)
- [Architecture](docs/architecture.md)
- [Principal Architecture Blueprint](docs/principal-architecture-blueprint.md)
- [Minikube Deployment Plan](docs/minikube-deployment-plan.md)
- [Architecture Decision Records](docs/adr)

## Architecture

```text
User or frontend
  -> backend-api
  -> ingestion-service
  -> analytics-engine
  -> recommendation-orchestrator
  -> agent-service
  -> OCI APIs and LLM providers
```

| Service | Responsibility | Status |
| --- | --- | --- |
| `backend-api` | Public REST API, frontend serving, request orchestration | Implemented |
| `frontend` | Browser UI for setup, dashboard, recommendations, and Copilot | Implemented as static assets |
| `ingestion-service` | OCI cost, usage, inventory, and metric ingestion | Planned |
| `analytics-engine` | Aggregations, forecasts, spend trends, anomaly signals | Planned |
| `recommendation-orchestrator` | Recommendation rules and AI workflow coordination | Planned |
| `agent-service` | LLM provider abstraction for Copilot and narrative recommendations | Planned |

Public clients should call only `backend-api`. Internal services should communicate through cluster-private Kubernetes services.

## Repository Layout

```text
apps/
  backend-api/                  # Public API service
  frontend/                     # Static frontend served by backend-api
  ingestion-service/            # Planned microservice
  analytics-engine/             # Planned microservice
  recommendation-orchestrator/  # Planned microservice
  agent-service/                # Planned microservice
k8s/
  base/backend-api.yaml         # Current Minikube-ready backend deployment
infra/
  terraform/oci/                # OCI API Gateway, Functions, IAM, and network scaffold
config/                         # Local configuration files
fixtures/                       # Mock/local data inputs
scripts/                        # Utility scripts
```

## Quick Start

### Local Python

```bash
cd apps/backend-api
PYTHONPATH=src python3 -m oci_cost_optimizer
```

Open:

```text
http://127.0.0.1:4310
```

### Docker Compose

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

### Minikube

```bash
minikube start
eval $(minikube docker-env)
docker build -f apps/backend-api/Dockerfile -t oci-cost-optimizer/backend-api:local .
kubectl create namespace oci-cost-optimizer --dry-run=client -o yaml | kubectl apply -f -
kubectl -n oci-cost-optimizer apply -f k8s/base/backend-api.yaml
kubectl -n oci-cost-optimizer rollout status deployment/backend-api
kubectl -n oci-cost-optimizer port-forward svc/backend-api 8080:80
```

Open:

```text
http://127.0.0.1:8080
```

## Current API Access

The current implemented API uses the `/api/v1` prefix. The older `/api` prefix remains as a temporary compatibility layer.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness status |
| `GET` | `/api/v1/ready` | Readiness and dependency status |
| `GET` | `/api/v1/version` | Service and API version metadata |
| `GET` | `/api/v1/status` | Combined service, readiness, dependency, and setup status |
| `GET` | `/api/v1/setup` | OCI and LLM setup status |
| `POST` | `/api/v1/setup/env-file` | Select a runtime `.env` file |
| `GET` | `/api/v1/dashboard?region=all&service=all` | Dashboard data |
| `GET` | `/api/v1/recommendations?region=all&service=all` | Recommendation data |
| `POST` | `/api/v1/copilot` | Ask the optimization assistant |

Examples:

```bash
curl -s http://127.0.0.1:8080/api/v1/health
curl -s http://127.0.0.1:8080/api/v1/ready
curl -s "http://127.0.0.1:8080/api/v1/dashboard?region=all&service=all"
curl -s "http://127.0.0.1:8080/api/v1/recommendations?region=all&service=Compute"
curl -s -X POST http://127.0.0.1:8080/api/v1/copilot \
  -H "Content-Type: application/json" \
  -d '{"question":"How can I reduce compute costs?","filters":{"region":"all","service":"Compute"}}'
```

For the detailed API contract, Minikube notes, request/response examples, and service flow, see [apps/backend-api/README.md](apps/backend-api/README.md).

## Target Enterprise API

The enterprise public API now uses `/api/v1`; typed schemas and OpenAPI documentation remain a planned hardening step:

| Method | Path | Owner |
| --- | --- | --- |
| `GET` | `/api/v1/health` | `backend-api` |
| `GET` | `/api/v1/ready` | `backend-api` |
| `GET` | `/api/v1/version` | `backend-api` |
| `GET` | `/api/v1/status` | `backend-api` |
| `GET` | `/api/v1/setup` | `backend-api` |
| `GET` | `/api/v1/dashboard` | `backend-api`, `analytics-engine` |
| `GET` | `/api/v1/recommendations` | `backend-api`, `recommendation-orchestrator` |
| `POST` | `/api/v1/copilot` | `backend-api`, `agent-service` |

Internal services should expose `/internal/v1/...` APIs over Kubernetes `ClusterIP` services only.

## Kubernetes Direction

Each microservice should own its deployment bundle:

- `Deployment`
- `Service`
- `ConfigMap`
- `Secret`
- `ServiceAccount`
- `NetworkPolicy`
- resource requests and limits
- health and readiness probes

Minikube should run one replica per service first. Only `backend-api` should be exposed from the laptop with `kubectl port-forward`, Minikube ingress, or a local API gateway.

## OCI Cloud Replica

The OCI replica of the AWS-style reference architecture is scaffolded in [infra/terraform/oci](infra/terraform/oci). It provisions OCI API Gateway, OCI Functions, OCIR, network resources, a Functions dynamic group, and IAM policies for cost retrieval, resource management, and AI advisor handlers.

Start with `enable_resource_mutation = false`, test read-only cost and recommendation flows first, then enable mutation policies only after approval workflow and audit logging are in place.

## Configuration

Common runtime variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_MODE` | `mock` | Runtime mode, usually `mock` or `oci` |
| `DATA_PROVIDER` | `mock` | Cost and inventory provider |
| `HOST` | `127.0.0.1` local, `0.0.0.0` container | Bind address |
| `PORT` | `4310` local, `8080` container | HTTP port |
| `LLM_PROVIDER` | `mock` | LLM provider adapter |
| `OPENAI_API_KEY` | empty | Required only for OpenAI-backed Copilot |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model name |

OCI-backed mode also needs OCI tenancy, user, fingerprint, region, config, and private key settings. In Kubernetes, use `Secret` objects for keys and tokens, `ConfigMap` objects for non-sensitive runtime settings, and read-only volume mounts for OCI key files.

## Enterprise Hardening

- Replace the current Python `http.server` implementation with FastAPI or another ASGI framework.
- Add OpenAPI documentation generated from typed request and response schemas.
- Split provider, analytics, recommendation, and LLM responsibilities into separate services.
- Add authentication, authorization, and audit logging before production use.
- Add correlation IDs, structured logs, metrics, and distributed tracing.
- Add Kubernetes network policies, resource limits, disruption budgets, and autoscaling.
- Keep local mock mode fast and deterministic so every service can run in Minikube on a laptop.

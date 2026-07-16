# Backend API Microservice

The backend API is the public entry point for the OCI Cost Optimizer platform. It serves the frontend, exposes cost and recommendation APIs, and will act as the API gateway/BFF while the enterprise services are split into independently deployable microservices.

Current implementation status:

- Implemented service: `backend-api`
- Local runtime: Python HTTP service
- Container runtime: Oracle Linux based image
- Kubernetes target: Minikube first, then enterprise Kubernetes or OKE
- Current API prefix: `/api/v1`
- Compatibility API prefix: `/api`

## Service Role

`backend-api` owns the external API contract and user-facing request orchestration.

It should not permanently own provider-specific cost collection, analytics, recommendation scoring, or LLM execution. Those concerns are expected to move behind internal microservice APIs:

| Service | Responsibility | Status |
| --- | --- | --- |
| `backend-api` | Public REST API, frontend serving, request orchestration | Implemented |
| `ingestion-service` | OCI cost, usage, inventory, and metric ingestion | Planned |
| `analytics-engine` | Aggregation, forecast, spend trends, anomaly signals | Planned |
| `recommendation-orchestrator` | Rule-based and AI-assisted recommendation workflow | Planned |
| `agent-service` | LLM provider abstraction and Copilot responses | Planned |

## Request Flow

```text
User or frontend
  -> backend-api
  -> ingestion-service
  -> analytics-engine
  -> recommendation-orchestrator
  -> agent-service
  -> OCI APIs and LLM providers
```

For the current local build, `backend-api` still performs mock data generation and Copilot responses in process. The API shape is intentionally close to the future service boundary so those implementations can be replaced by internal service calls later.

## API Access

### Local Python

```bash
cd apps/backend-api
PYTHONPATH=src python3 -m oci_cost_optimizer
```

Base URL:

```text
http://127.0.0.1:4310
```

### Docker Compose

From the repository root:

```bash
docker compose up --build
```

Base URL:

```text
http://127.0.0.1:8080
```

### Minikube

Start Minikube and build the image inside the Minikube Docker daemon:

```bash
minikube start
eval $(minikube docker-env)
docker build -f apps/backend-api/Dockerfile -t oci-cost-optimizer/backend-api:local .
```

Deploy the backend API:

```bash
kubectl create namespace oci-cost-optimizer --dry-run=client -o yaml | kubectl apply -f -
kubectl -n oci-cost-optimizer apply -f k8s/base/backend-api.yaml
kubectl -n oci-cost-optimizer rollout status deployment/backend-api
```

Access the service from the laptop:

```bash
kubectl -n oci-cost-optimizer port-forward svc/backend-api 8080:80
```

Base URL:

```text
http://127.0.0.1:8080
```

Check the running pod:

```bash
kubectl -n oci-cost-optimizer get pods
kubectl -n oci-cost-optimizer logs deployment/backend-api
```

## Current API Endpoints

These endpoints are implemented today under `/api/v1`. The older `/api` paths remain available as a temporary compatibility layer and return deprecation headers.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness probe and basic service status |
| `GET` | `/api/v1/ready` | Readiness and dependency status |
| `GET` | `/api/v1/version` | Service and API version metadata |
| `GET` | `/api/v1/status` | Combined service, readiness, dependency, and setup status |
| `GET` | `/api/v1/setup` | OCI and LLM setup status |
| `POST` | `/api/v1/setup/env-file` | Select a runtime `.env` file |
| `GET` | `/api/v1/dashboard?region=all&service=all` | Dashboard summary, cost trends, resources, recommendations |
| `GET` | `/api/v1/recommendations?region=all&service=all` | Recommendation list only |
| `POST` | `/api/v1/copilot` | Ask the cost optimization assistant |

### Health

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

Example response:

```json
{
  "ok": true,
  "mode": "mock",
  "service": "oci-cost-optimizer-backend"
}
```

### Readiness

```bash
curl -s http://127.0.0.1:8080/api/v1/ready
```

Example response shape:

```json
{
  "ready": true,
  "checks": [],
  "dependencies": {
    "database": "mock",
    "cache": "mock",
    "llm": "mock"
  }
}
```

### Setup Status

```bash
curl -s http://127.0.0.1:8080/api/v1/setup
```

Use this before enabling OCI-backed mode. It reports whether OCI configuration, key files, and LLM configuration are available to the running service.

### Select Runtime Env File

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/setup/env-file \
  -H "Content-Type: application/json" \
  -d '{"path":"/config/local.env"}'
```

In Docker or Kubernetes, the path must exist inside the container. For Minikube, mount or create a Kubernetes `Secret`/`ConfigMap` instead of depending on a host-only path.

### Dashboard

```bash
curl -s "http://127.0.0.1:8080/api/v1/dashboard?region=all&service=all"
```

Query parameters:

| Parameter | Example | Description |
| --- | --- | --- |
| `region` | `all`, `us-ashburn-1` | Filters dashboard data by OCI region |
| `service` | `all`, `Compute`, `Storage` | Filters dashboard data by service name |

Response shape:

```json
{
  "meta": {
    "mode": "mock",
    "tenancy": "example",
    "period": "last 30 days",
    "filters": {
      "region": "all",
      "service": "all"
    }
  },
  "summary": {},
  "dailyCosts": [],
  "forecast": [],
  "spendByService": {},
  "spendByCompartment": {},
  "resources": [],
  "recommendations": []
}
```

### Recommendations

```bash
curl -s "http://127.0.0.1:8080/api/v1/recommendations?region=all&service=Compute"
```

Response shape:

```json
{
  "meta": {},
  "recommendations": [
    {
      "id": "rec-001",
      "title": "Resize underutilized compute instance",
      "severity": "high",
      "estimatedMonthlySavings": 120.0,
      "service": "Compute",
      "region": "us-ashburn-1",
      "actions": []
    }
  ]
}
```

### Copilot

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/copilot \
  -H "Content-Type: application/json" \
  -d '{"question":"How can I reduce compute costs?","filters":{"region":"all","service":"Compute"}}'
```

Request body:

```json
{
  "question": "How can I reduce compute costs?",
  "filters": {
    "region": "all",
    "service": "Compute"
  }
}
```

Response shape:

```json
{
  "answer": "Potential savings are available in Compute...",
  "mode": "mock"
}
```

## Enterprise API Contract

The current public contract is versioned. OpenAPI-backed typed schemas remain a planned hardening step:

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
| `POST` | `/internal/v1/ingestion/runs` | `ingestion-service` |
| `GET` | `/internal/v1/analytics/spend` | `analytics-engine` |
| `POST` | `/internal/v1/recommendations/evaluate` | `recommendation-orchestrator` |
| `POST` | `/internal/v1/agents/copilot` | `agent-service` |

Public clients should only call `backend-api`. Internal service endpoints should remain cluster-private.

## Kubernetes Design

Each microservice should have its own Kubernetes objects:

- `Deployment`
- `Service`
- `ConfigMap`
- `Secret`
- `ServiceAccount`
- `NetworkPolicy`
- `HorizontalPodAutoscaler` when metrics are available

For local Minikube, start with one replica per service and `ClusterIP` services. Expose only `backend-api` through `kubectl port-forward`, Minikube ingress, or a local gateway.

Suggested service DNS names:

```text
backend-api.oci-cost-optimizer.svc.cluster.local
ingestion-service.oci-cost-optimizer.svc.cluster.local
analytics-engine.oci-cost-optimizer.svc.cluster.local
recommendation-orchestrator.oci-cost-optimizer.svc.cluster.local
agent-service.oci-cost-optimizer.svc.cluster.local
```

## Configuration

Common runtime variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `oci-cost-optimizer-backend` | Service name in health responses |
| `APP_MODE` | `mock` | Runtime mode, usually `mock` or `oci` |
| `DATA_PROVIDER` | `mock` | Cost and inventory provider |
| `HOST` | `127.0.0.1` local, `0.0.0.0` container | Bind address |
| `PORT` | `4310` local, `8080` container | HTTP port |
| `STATIC_ROOT` | `apps/frontend` local, `/app/frontend` container | Frontend files |
| `LLM_PROVIDER` | `mock` | LLM provider adapter |
| `OPENAI_API_KEY` | empty | Required only for OpenAI-backed Copilot |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model name |

OCI variables for OCI-backed mode:

| Variable | Description |
| --- | --- |
| `OCI_TENANCY_OCID` | OCI tenancy OCID |
| `OCI_USER_OCID` | OCI user OCID |
| `OCI_FINGERPRINT` | API key fingerprint |
| `OCI_REGION` | OCI home or target region |
| `OCI_KEY_FILE` | Path to private key inside the runtime |
| `OCI_CONFIG_FILE` | OCI config path, default `/oci/config` in Docker |
| `OCI_PROFILE` | OCI config profile, default `DEFAULT` |

For Kubernetes, store secrets in a `Secret`, non-sensitive settings in a `ConfigMap`, and mount OCI keys as read-only files.

## Enterprise Hardening Checklist

- Replace `http.server` with FastAPI or another ASGI framework.
- Generate OpenAPI docs from typed request and response models.
- Add authentication and authorization before enabling production setup mutation endpoints.
- Move OCI collection into `ingestion-service`.
- Move aggregation and forecast logic into `analytics-engine`.
- Move recommendation scoring into `recommendation-orchestrator`.
- Move LLM prompts and provider calls into `agent-service`.
- Add structured logs with correlation IDs across service calls.
- Add metrics, traces, request timing, and error budgets.
- Add resource requests/limits and pod disruption budgets.
- Add network policies so only `backend-api` can receive external traffic.

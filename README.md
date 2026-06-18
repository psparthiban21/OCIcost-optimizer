# OCI Cost Optimizer AI Recommendation

This project will build an OCI Cost Optimizer dashboard with LLM-assisted recommendations.

The first delivery target is a standalone local Python/Node-style app for personal development and demos. It runs on a Mac laptop without Kubernetes, external databases, or cloud credentials.

Later targets can still add Minikube and OCI-managed infrastructure, keeping the same API and service boundaries where possible.

## Architecture Docs

- [Architecture](./docs/architecture.md)
- [Principal Architecture Blueprint](./docs/principal-architecture-blueprint.md)
- [Minikube Deployment Plan](./docs/minikube-deployment-plan.md)
- [Dashboard Template Direction](./docs/dashboard-template.md)
- [Architecture Decision Records](./docs/adr)

## Frontend Prototype

- [OCI Cost Optimizer HTML Prototype](./prototypes/oci-cost-optimizer.html)

The HTML prototype must remain a standalone mock-mode fallback so the dashboard can still be shown if Minikube or backend services are unavailable.

## Local Standalone Application

The first app is implemented as a Python mock backend that serves the dashboard frontend and API from one local process. It is available without installing dependencies:

```bash
cd apps/backend-api
PYTHONPATH=src python3 -m oci_cost_optimizer
```

Then open:

```text
http://127.0.0.1:4310
```

The mock server serves the dashboard frontend and exposes deterministic mock endpoints:

- `GET /api/health`
- `GET /api/ready`
- `GET /api/dashboard?region=all&service=all`
- `GET /api/recommendations?region=all&service=all`
- `POST /api/copilot`

Container build from the repository root:

```bash
docker build -f apps/backend-api/Dockerfile -t oci-cost-optimizer/backend-api:local .
```

## Docker Desktop Run

The container is designed to run with a small local footprint:

- Memory limit: `2 GB`
- CPU limit: `1 CPU`
- Process limit: `256`

Build and run with Docker Compose:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

Stop:

```bash
docker compose down
```

Equivalent `docker run` command:

```bash
docker build -f apps/backend-api/Dockerfile -t oci-cost-optimizer/backend-api:local .
docker run --rm \
  --name oci-cost-optimizer \
  --memory=2g \
  --cpus=1 \
  --pids-limit=256 \
  -p 8080:8080 \
  --env-file .env \
  -e HOST=0.0.0.0 \
  -e PORT=8080 \
  -e OCI_CLI_PATH=oci \
  -e OCI_CONFIG_FILE=/oci/config \
  -v "$PWD/.oci:/oci:ro" \
  oci-cost-optimizer/backend-api:local
```

The app also exposes setup assistance at:

```text
http://127.0.0.1:8080/api/setup
```

The dashboard shows a setup banner if OCI live mode is selected but required details are missing.

## New Laptop First Run

The app can start before the user has OCI or OpenAI credentials. The recommended first run is mock mode:

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8080
```

When a user wants live OCI data, they can either mount an OCI CLI config or enter individual values in `.env`. The app assists through:

```text
http://127.0.0.1:8080/api/setup
```

The dashboard also shows a setup banner with missing items. It never prints secret values; it reports only `set` or `missing`.

For OpenAI-backed recommendations, the user sets:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Keep OpenAI keys in `.env` only. Do not commit them.

## Local Git State

This project is tracked in a local Git repository. Check the current state:

```bash
git status
```

Save a new checkpoint:

```bash
git add .
git commit -m "Describe the change"
```

Show recent checkpoints:

```bash
git log --oneline --max-count=10
```

Revert a committed change without rewriting history:

```bash
git revert <commit-sha>
```

For the initial baseline, the first commit is:

```text
b7727f5 Initial standalone OCI cost optimizer app
```

## Phase 1 Scope

- Run as a single local process.
- Serve the dashboard from `apps/frontend`.
- Use deterministic mock OCI cost, usage, inventory, and recommendation data.
- Keep API routes shaped like the later production backend.
- Add real OCI, database, queue, and LLM integrations behind adapters after the local workflow feels useful.

## Local Secrets and OCI Config

Use `.env` for local-only credentials and account identifiers. Start from the example file:

```bash
cp .env.example .env
```

Then put your OCI tenancy OCID and other local credentials in `.env`. The tenancy OCID you provided belongs in:

```bash
OCI_TENANCY_OCID=ocid1.tenancy.oc1..aaaaaaaagfnp3wexxeiqiozketi5rlismcclwqewd4hzhn7xndkpay6uobjq
OCI_REGION=ap-mumbai-1
```

Do not commit `.env`, private keys, auth tokens, or API keys.

For Docker live OCI mode, use one of these setup patterns.

Pattern A: mount an OCI CLI config and key into the container:

```text
.oci/
  config
  oci_api_key.pem
```

Inside `.oci/config`, the key path must be a container path:

```ini
[DEFAULT]
user=ocid1.user.oc1..example
fingerprint=aa:bb:cc:dd:ee:ff
tenancy=ocid1.tenancy.oc1..example
region=ap-mumbai-1
key_file=/oci/oci_api_key.pem
```

Pattern B: provide individual values in `.env`. The app can generate a runtime OCI CLI config when all of these are set:

```bash
DATA_PROVIDER=oci
OCI_USER_OCID=ocid1.user.oc1..example
OCI_FINGERPRINT=aa:bb:cc:dd:ee:ff
OCI_TENANCY_OCID=ocid1.tenancy.oc1..example
OCI_REGION=ap-mumbai-1
OCI_KEY_FILE=/oci/oci_api_key.pem
```

In both patterns, mount the key file so `/oci/oci_api_key.pem` exists inside the container.

## Local OCI CLI

The OCI CLI can be installed into the project virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip oci-cli
```

This project uses a local ignored OCI config at `.oci/config`, generated from `.env`.

Verify access to the Mumbai region:

```bash
.venv/bin/oci iam region list --config-file .oci/config --auth api_key --query "data[?name=='ap-mumbai-1']"
```

To show live OCI inventory in the standalone dashboard, set this in `.env`:

```bash
DATA_PROVIDER=oci
```

Then restart the backend. The dashboard will use OCI Search for live resources and OCI Usage API for cost rows when billing data is available to the API key.

## Planned Capabilities

- OCI cost, usage, inventory, and utilization ingestion.
- Deterministic cost analytics.
- LLM-backed recommendation agents.
- PostgreSQL-backed state management.
- Redis-backed cache and local queue.
- Dashboard workflow for review, approval, rejection, and tracking.
- Optional Minikube deployment with an OCI migration path.

## Suggested Next Step

Build out the standalone local app before adding distributed services:

```text
apps/
  frontend/
  backend-api/
  local-data/
docs/
  adr/
```

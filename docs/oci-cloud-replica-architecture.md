# OCI Cost Optimizer Dashboard: Project Architecture

This is the Oracle Cloud replica of the AWS reference architecture in the design image. The shape is intentionally similar: a dashboard calls an API gateway, the gateway fans out to serverless handlers, handlers use cloud cost/resource APIs, and Terraform/OCI Resource Manager owns repeatable deployment.

## AWS to OCI Mapping

| AWS reference component | OCI equivalent |
| --- | --- |
| Streamlit web app | Static dashboard, Streamlit container, or frontend served by `backend-api` |
| AWS API Gateway | OCI API Gateway |
| Lambda: Cost Retriever | OCI Function: `cost-retriever` |
| Lambda: Resource Manager | OCI Function: `resource-manager` |
| Lambda: AI Agent | OCI Function: `ai-advisor` |
| AWS Cost Explorer | OCI Usage API and Cost Analysis exports |
| Boto3 resource actions | OCI SDK, OCI CLI, or Resource Principal calls |
| EC2 | OCI Compute instances |
| RDS | OCI Database, Autonomous Database, MySQL HeatWave |
| S3 | OCI Object Storage |
| OpenAI API | OCI Generative AI or approved OpenAI-compatible provider |
| Terraform | Terraform with OCI provider or OCI Resource Manager |

## Target OCI Architecture

```mermaid
flowchart TB
  UI["User Interface<br/>Dashboard Web App"] --> CostUI["Cost Dashboard<br/>Charts"]
  UI --> ResourceUI["Resource Control<br/>Compute, DB, Object Storage"]
  UI --> AdvisorUI["AI Cost Advisor<br/>Chatbot"]

  subgraph OCI["Oracle Cloud Infrastructure"]
    APIGW["OCI API Gateway"]
    CostFn["OCI Function<br/>Cost Retriever"]
    ResourceFn["OCI Function<br/>Resource Manager"]
    AdvisorFn["OCI Function<br/>AI Advisor"]
    Tools["OCI SDK / CLI Tool Layer"]
    Usage["OCI Usage API<br/>Cost and Usage"]
    Search["OCI Resource Search"]
    Monitoring["OCI Monitoring"]
    Compute["OCI Compute"]
    Database["OCI Database / ADB"]
    ObjectStorage["OCI Object Storage"]
    GenAI["OCI Generative AI<br/>or OpenAI Provider"]
    Registry["OCI Container Registry"]
    Vault["OCI Vault"]
    Logs["OCI Logging"]
  end

  Terraform["Terraform / OCI Resource Manager"] --> APIGW
  Terraform --> CostFn
  Terraform --> ResourceFn
  Terraform --> AdvisorFn
  Terraform --> Registry
  Terraform --> Vault

  CostUI --> APIGW
  ResourceUI --> APIGW
  AdvisorUI --> APIGW

  APIGW --> CostFn
  APIGW --> ResourceFn
  APIGW --> AdvisorFn

  CostFn --> Usage
  CostFn --> Search
  CostFn --> Monitoring

  ResourceFn --> Tools
  AdvisorFn --> Tools
  AdvisorFn --> GenAI

  Tools --> Usage
  Tools --> Search
  Tools --> Monitoring
  Tools --> Compute
  Tools --> Database
  Tools --> ObjectStorage

  CostFn --> Logs
  ResourceFn --> Logs
  AdvisorFn --> Logs
```

## Database-Centric Data Flow

PostgreSQL is the target system of record for normalized OCI cost data, inventory snapshots, analytics findings, recommendations, evidence, user decisions, and agent runs. Redis sits beside it for cache-aside dashboard reads and lightweight local queue semantics; in OCI, the queue role can move to OCI Queue or OCI Streaming while Redis remains the hot-read cache.

```mermaid
flowchart LR
  subgraph Sources["OCI and Local Sources"]
    Scheduler["Scheduler / CronJob"]
    Fixtures["Fixture / Mock Loader"]
    Usage["OCI Usage API<br/>Cost and Usage"]
    Search["OCI Resource Search"]
    Monitoring["OCI Monitoring"]
  end

  subgraph Processing["Processing Pipeline"]
    Ingest["Ingestion Service<br/>or Cost Retriever Function"]
    Analytics["Cost Analytics Engine<br/>deterministic findings"]
    Orchestrator["Recommendation Orchestrator"]
    Agents["AI Agent Services"]
    LLM["LLM Provider<br/>OCI Generative AI or approved provider"]
  end

  subgraph State["State and Coordination"]
    Postgres[("PostgreSQL / OCI Relational DB<br/>system of record")]
    Redis[("Redis / OCI Cache<br/>dashboard cache")]
    Queue["Redis Streams locally<br/>OCI Queue or Streaming in OCI"]
  end

  subgraph Consumers["Consumers"]
    API["Backend API / API Gateway Handlers"]
    UI["Dashboard UI"]
    Actions["Recommendation Action Workflow"]
  end

  Scheduler --> Ingest
  Fixtures --> Ingest
  Usage --> Ingest
  Search --> Ingest
  Monitoring --> Ingest

  Ingest -->|normalized cost, usage, inventory, utilization| Postgres
  Ingest -->|data_refreshed| Queue
  Ingest -->|invalidate stale summaries| Redis

  Queue --> Analytics
  Analytics -->|read normalized records| Postgres
  Analytics -->|analytics_findings| Postgres
  Analytics -->|findings_ready| Queue

  Queue --> Orchestrator
  Orchestrator --> Agents
  Agents --> LLM
  Agents --> Orchestrator
  Orchestrator -->|recommendations, evidence, agent_runs| Postgres
  Orchestrator -->|recommendation_ready and cache refresh| Queue
  Orchestrator --> Redis

  UI --> API
  API -->|cache-aside reads| Redis
  API -->|authoritative reads and writes| Postgres
  API -->|approve, reject, assign, schedule| Actions
  Actions -->|recommendation_actions audit history| Postgres
```

Database write ownership:

- Ingestion writes `cost_daily`, `usage_daily`, `resources`, `resource_snapshots`, and `utilization_metrics`.
- Analytics reads normalized records and writes `analytics_findings`.
- The recommendation orchestrator writes `recommendations`, `recommendation_evidence`, and `agent_runs`.
- The API writes user-driven `recommendation_actions` and reads PostgreSQL as the authoritative fallback when Redis misses.

Current repository note: `backend-api` presently serves the dashboard contract from mock data or the live OCI adapter. The diagram above shows the target flow once the ingestion, analytics, recommendation, PostgreSQL, and Redis services are introduced behind the same `/api/v1` browser contract.

## API Gateway Routes

The gateway should expose the same public contract used by the app:

| Route | Backend | Purpose |
| --- | --- | --- |
| `GET /api/v1/health` | `backend-api` or health function | Liveness |
| `GET /api/v1/dashboard` | `cost-retriever` | Cost summary, trends, inventory, recommendations |
| `GET /api/v1/recommendations` | `ai-advisor` or `backend-api` | Recommendation list |
| `POST /api/v1/copilot` | `ai-advisor` | Chat and narrative advice |
| `POST /api/v1/resources/actions` | `resource-manager` | Stop, resize, tag, lifecycle, or policy actions |

For the current repository, `backend-api` remains the fastest deployable unit because it already serves the frontend and `/api/v1` contract. The serverless split can be introduced incrementally behind OCI API Gateway without changing the browser contract.

## Function Responsibilities

### Cost Retriever

- Read OCI Usage API for daily cost and service grouping.
- Read Resource Search for resource inventory.
- Read Monitoring metrics for utilization signals.
- Normalize data into the dashboard shape currently returned by `/api/v1/dashboard`.

### Resource Manager

- Accept only validated, auditable action requests.
- Support dry-run by default.
- Execute approved actions through OCI SDK with Resource Principal identity.
- Start with low-risk actions: add tags, apply object lifecycle policy, stop explicitly approved compute instances.

### AI Advisor

- Consume structured findings from cost analytics.
- Produce plain-language recommendation summaries.
- Use OCI Generative AI by default for OCI-only deployments.
- Optionally use OpenAI when enterprise policy allows it.
- Never mutate OCI resources directly.

## IAM Model

Use Resource Principals for Functions. Terraform creates a dynamic group for functions in the deployment compartment and grants least-privilege read policies first.

Recommended first policy surface:

- inspect compartments
- read usage reports
- read resource inventory/search results
- read metrics
- use OCI Generative AI
- manage selected resource families only when `enable_resource_mutation = true`

High-risk actions should require human approval and should be kept disabled in the first OCI deployment.

## Deployment Tracks

### Track A: Fastest OCI Replica

1. Build and push the existing `backend-api` image to OCI Container Registry.
2. Run it on OKE or OCI Container Instances.
3. Put OCI API Gateway or Load Balancer in front of it.
4. Enable `DATA_PROVIDER=oci`.
5. Use OCI config locally first, then move to Resource Principal or workload identity.

### Track B: Serverless Replica of the AWS Diagram

1. Build function images for `cost-retriever`, `resource-manager`, and `ai-advisor`.
2. Push them to OCI Container Registry.
3. Deploy OCI Functions application and API Gateway with Terraform.
4. Wire `/api/v1/dashboard`, `/api/v1/copilot`, and resource action routes to functions.
5. Move shared data contracts from `backend-api` into a common Python package.

## Repository Setup

The Terraform scaffold lives in:

```text
infra/terraform/oci
```

Use it as the OCI control plane foundation. It creates the network, container repository, Functions application, three functions, API Gateway, deployment routes, dynamic group, and IAM policies.

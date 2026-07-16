# Project Structure

```text
.
├── apps/
│   ├── frontend/                    # Dashboard UI
│   └── backend-api/                 # Local standalone API and static frontend server
├── docs/
│   ├── adr/                         # Architecture decision records
│   ├── architecture.md
│   ├── dashboard-template.md
│   ├── minikube-deployment-plan.md
│   ├── oci-cloud-replica-architecture.md
│   └── principal-architecture-blueprint.md
├── fixtures/                        # Future local mock cost, usage, and inventory files
├── infra/
│   └── terraform/
│       └── oci/                     # OCI API Gateway, Functions, network, and IAM scaffold
├── k8s/
│   └── base/                        # Optional later Minikube/OKE manifests
├── prototypes/
│   └── oci-cost-optimizer.html      # Standalone mock dashboard fallback
├── scripts/                         # Local helper scripts
├── README.md
└── PROJECT_STRUCTURE.md
```

The initial mock application has been added:

- `apps/backend-api/src/oci_cost_optimizer/mock_data.py` contains deterministic OCI-like cost, inventory, recommendation, and Copilot fixture logic.
- `apps/backend-api/src/oci_cost_optimizer/server.py` serves mock API endpoints and the static dashboard frontend.
- `apps/frontend/` contains the API-shaped mock dashboard.
- `k8s/base/backend-api.yaml` contains optional later Minikube/OKE-style Deployment and Service material.
- `infra/terraform/oci/` contains the OCI cloud replica setup for API Gateway, Functions, OCIR, networking, and IAM.
- `prototypes/oci-cost-optimizer.html` remains the standalone fallback dashboard.

# OCI Serverless Replica Terraform

This folder provisions an Oracle Cloud replica of the AWS-style cost optimizer architecture:

- OCI API Gateway
- OCI Functions application
- `cost-retriever` function
- `resource-manager` function
- `ai-advisor` function
- OCIR container repository
- OCI Vault, KMS key, and optional secrets
- VCN, subnet, internet gateway, route table, and security list
- Dynamic group and IAM policies for Function resource principals

The first apply should keep `enable_resource_mutation = false`. That creates read/advisory capability without granting resource-changing permissions.

The gateway defaults to `PRIVATE`, and subnet ingress defaults to the VCN CIDR. For a public demo, explicitly set `api_gateway_endpoint_type = "PUBLIC"` and restrict `api_gateway_ingress_cidr` to your office/VPN egress CIDR rather than `0.0.0.0/0`.

## Prerequisites

- Terraform `>= 1.5`
- OCI tenancy and compartment OCIDs
- OCI user API key for Terraform, or adapt the provider for OCI Resource Manager
- Three function images pushed to OCIR:
  - `cost-retriever`
  - `resource-manager`
  - `ai-advisor`

The current repository already has the backend logic for mock and OCI-backed data. The function images can initially wrap those Python modules, then split into independent packages as the architecture matures.

## Configure

```bash
cd infra/terraform/oci
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with real OCI values and OCIR image names.

For a Mumbai-region deployment, the region is:

```hcl
region = "ap-mumbai-1"
```

## Deploy

```bash
terraform init
terraform plan
terraform apply
```

After apply, Terraform prints:

- `api_gateway_endpoint`
- `api_v1_base_url`
- function OCIDs
- dynamic group name
- Vault and KMS key OCIDs
- secret OCIDs when secret content or an existing secret OCID was supplied

## Vault and Secrets

By default, Terraform creates:

- `oci_kms_vault.optimizer`
- `oci_kms_key.optimizer`

Terraform creates these secrets only when you provide base64 content:

- `oci_vault_secret.openai_api_key`
- `oci_vault_secret.database_password`

Examples:

```bash
printf '%s' 'your-openai-key' | base64
printf '%s' 'your-database-password' | base64
```

Paste those values into:

```hcl
openai_api_key_secret_content_base64     = "..."
database_password_secret_content_base64  = "..."
```

If you already have a Vault secret, set `openai_api_key_secret_ocid` instead. The Functions app receives only secret OCIDs in environment variables, not plaintext secret values.

The Functions dynamic group receives:

```text
read secret-family in the deployment compartment
```

That allows runtime secret retrieval through Resource Principal identity.

## Gateway Contract

The API Gateway deployment owns `/api/v1` and maps routes to Functions:

| Route | Function |
| --- | --- |
| `GET /api/v1/health` | `cost-retriever` |
| `GET /api/v1/dashboard` | `cost-retriever` |
| `GET /api/v1/recommendations` | `ai-advisor` |
| `POST /api/v1/copilot` | `ai-advisor` |
| `POST /api/v1/resources/actions` | `resource-manager` |

## First Implementation Path

1. Keep the local app as the contract reference.
2. Build small OCI Function handlers that call the existing `oci_cost_optimizer` modules.
3. Push function images to OCIR.
4. Apply this Terraform.
5. Test `GET <api_v1_base_url>/health`.
6. Test `GET <api_v1_base_url>/dashboard?region=all&service=all`.
7. Add authentication and request validation before exposing action routes to broader users.

## Production Hardening

- Put API Gateway behind a custom domain and WAF policy.
- Enable IAM/JWT authorizers for user-facing APIs.
- Move secrets to OCI Vault.
- Add OCI Logging log groups and alarms.
- Use private endpoint type where enterprise networking allows it.
- Keep mutation policies disabled until approval workflow and audit logging are implemented.

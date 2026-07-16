output "api_gateway_endpoint" {
  description = "OCI API Gateway deployment endpoint. If api_gateway_endpoint_type is PRIVATE, this URL is reachable only from private network paths into the VCN."
  value       = oci_apigateway_deployment.optimizer.endpoint
}

output "api_v1_base_url" {
  description = "Versioned API base URL."
  value       = oci_apigateway_deployment.optimizer.endpoint
}

output "container_repository_path" {
  description = "OCIR repository path reserved for cost optimizer function images."
  value       = oci_artifacts_container_repository.functions.display_name
}

output "functions_application_id" {
  description = "OCI Functions application OCID."
  value       = oci_functions_application.optimizer.id
}

output "cost_retriever_function_id" {
  description = "Cost retriever function OCID."
  value       = oci_functions_function.cost_retriever.id
}

output "resource_manager_function_id" {
  description = "Resource manager function OCID."
  value       = oci_functions_function.resource_manager.id
}

output "ai_advisor_function_id" {
  description = "AI advisor function OCID."
  value       = oci_functions_function.ai_advisor.id
}

output "functions_dynamic_group_name" {
  description = "Dynamic group name used by Function resource principals."
  value       = oci_identity_dynamic_group.functions.name
}

output "vault_id" {
  description = "OCI Vault OCID when create_vault is true."
  value       = try(oci_kms_vault.optimizer[0].id, null)
}

output "secrets_key_id" {
  description = "OCI KMS key OCID used to encrypt secrets when create_vault is true."
  value       = try(oci_kms_key.optimizer[0].id, null)
}

output "openai_api_key_secret_id" {
  description = "OpenAI API key secret OCID. Null unless an existing secret OCID or secret content was provided."
  value       = local.openai_secret_id != "" ? local.openai_secret_id : null
  sensitive   = true
}

output "database_password_secret_id" {
  description = "Database password secret OCID. Null unless secret content was provided."
  value       = local.database_password_secret_id != "" ? local.database_password_secret_id : null
  sensitive   = true
}

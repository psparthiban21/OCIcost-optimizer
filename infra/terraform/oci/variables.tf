variable "tenancy_ocid" {
  description = "OCI tenancy OCID."
  type        = string
}

variable "user_ocid" {
  description = "OCI user OCID used by Terraform. Leave empty when running from OCI Resource Manager with instance/resource principal support added."
  type        = string
  default     = ""
  sensitive   = true
}

variable "fingerprint" {
  description = "API key fingerprint for the Terraform user."
  type        = string
  default     = ""
  sensitive   = true
}

variable "private_key" {
  description = "PEM private key content for the Terraform user."
  type        = string
  default     = ""
  sensitive   = true
}

variable "region" {
  description = "OCI region, for example ap-mumbai-1."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment where API Gateway, Functions, networking, and repositories are created."
  type        = string
}

variable "target_resource_compartment_ocid" {
  description = "Compartment containing resources the optimizer may inspect or mutate. Defaults to deployment compartment when empty."
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Short name used for OCI resource display names."
  type        = string
  default     = "oci-cost-optimizer"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "vcn_cidr" {
  description = "CIDR for the optimizer VCN."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR for the public subnet used by API Gateway and Functions."
  type        = string
  default     = "10.42.10.0/24"
}

variable "api_gateway_ingress_cidr" {
  description = "CIDR allowed to reach the API Gateway subnet on 443. Leave empty to restrict to the VCN CIDR."
  type        = string
  default     = ""
}

variable "cost_retriever_image" {
  description = "Container image for the cost retriever function."
  type        = string
}

variable "resource_manager_image" {
  description = "Container image for the resource manager function."
  type        = string
}

variable "ai_advisor_image" {
  description = "Container image for the AI advisor function."
  type        = string
}

variable "llm_provider" {
  description = "LLM provider used by the AI advisor function."
  type        = string
  default     = "oci-generative-ai"
}

variable "openai_api_key_secret_ocid" {
  description = "Optional OCI Vault secret OCID for OpenAI API key when llm_provider is openai."
  type        = string
  default     = ""
  sensitive   = true
}

variable "create_vault" {
  description = "Create an OCI Vault and encryption key for application secrets."
  type        = bool
  default     = true
}

variable "vault_type" {
  description = "OCI Vault type. DEFAULT is lower cost; VIRTUAL_PRIVATE provides dedicated isolation at higher cost."
  type        = string
  default     = "DEFAULT"

  validation {
    condition     = contains(["DEFAULT", "VIRTUAL_PRIVATE"], var.vault_type)
    error_message = "vault_type must be DEFAULT or VIRTUAL_PRIVATE."
  }
}

variable "openai_api_key_secret_content_base64" {
  description = "Optional base64-encoded OpenAI API key. When set and create_vault is true, Terraform creates an OCI Vault secret."
  type        = string
  default     = ""
  sensitive   = true
}

variable "database_password_secret_content_base64" {
  description = "Optional base64-encoded database password reserved for future database-backed state."
  type        = string
  default     = ""
  sensitive   = true
}

variable "enable_resource_mutation" {
  description = "Enable IAM policy statements that allow resource-changing actions. Keep false for the first deployment."
  type        = bool
  default     = false
}

variable "api_gateway_endpoint_type" {
  description = "API Gateway endpoint type. Use PUBLIC for laptop demos and PRIVATE for private enterprise networks."
  type        = string
  default     = "PRIVATE"

  validation {
    condition     = contains(["PUBLIC", "PRIVATE"], var.api_gateway_endpoint_type)
    error_message = "api_gateway_endpoint_type must be PUBLIC or PRIVATE."
  }
}

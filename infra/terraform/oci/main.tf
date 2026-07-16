locals {
  name_prefix                 = "${var.project_name}-${var.environment}"
  target_resource_compartment = var.target_resource_compartment_ocid != "" ? var.target_resource_compartment_ocid : var.compartment_ocid
  functions_dynamic_group     = "${local.name_prefix}-functions"
  generated_openai_secret_id  = try(oci_vault_secret.openai_api_key[0].id, "")
  openai_secret_id            = var.openai_api_key_secret_ocid != "" ? var.openai_api_key_secret_ocid : local.generated_openai_secret_id
  database_password_secret_id = try(oci_vault_secret.database_password[0].id, "")
  gateway_ingress_cidr        = var.api_gateway_ingress_cidr != "" ? var.api_gateway_ingress_cidr : var.vcn_cidr

  function_config = {
    APP_MODE                             = "oci"
    DATA_PROVIDER                        = "oci"
    OCI_TENANCY_OCID                     = var.tenancy_ocid
    OCI_REGION                           = var.region
    LLM_PROVIDER                         = var.llm_provider
    OPENAI_API_KEY_SECRET_OCID           = local.openai_secret_id
    DATABASE_PASSWORD_SECRET_OCID        = local.database_password_secret_id
    ENABLE_RUNTIME_SECRET_RETRIEVAL      = "true"
    ENABLE_PLAINTEXT_ENVIRONMENT_SECRETS = "false"
  }

  readonly_policy_statements = [
    "Allow dynamic-group ${local.functions_dynamic_group} to inspect compartments in tenancy",
    "Allow dynamic-group ${local.functions_dynamic_group} to read usage-reports in tenancy",
    "Allow dynamic-group ${local.functions_dynamic_group} to read metrics in compartment id ${local.target_resource_compartment}",
    "Allow dynamic-group ${local.functions_dynamic_group} to read all-resources in compartment id ${local.target_resource_compartment}",
    "Allow dynamic-group ${local.functions_dynamic_group} to use generative-ai-family in tenancy",
    "Allow dynamic-group ${local.functions_dynamic_group} to read secret-family in compartment id ${var.compartment_ocid}"
  ]

  mutation_policy_statements = [
    "Allow dynamic-group ${local.functions_dynamic_group} to manage instance-family in compartment id ${local.target_resource_compartment}",
    "Allow dynamic-group ${local.functions_dynamic_group} to manage volume-family in compartment id ${local.target_resource_compartment}",
    "Allow dynamic-group ${local.functions_dynamic_group} to manage object-family in compartment id ${local.target_resource_compartment}",
    "Allow dynamic-group ${local.functions_dynamic_group} to manage database-family in compartment id ${local.target_resource_compartment}"
  ]
}

resource "oci_core_vcn" "optimizer" {
  compartment_id = var.compartment_ocid
  cidr_block     = var.vcn_cidr
  display_name   = "${local.name_prefix}-vcn"
  dns_label      = "costopt"
}

resource "oci_core_internet_gateway" "optimizer" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-igw"
  vcn_id         = oci_core_vcn.optimizer.id
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-public-rt"
  vcn_id         = oci_core_vcn.optimizer.id

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.optimizer.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-public-sl"
  vcn_id         = oci_core_vcn.optimizer.id

  ingress_security_rules {
    protocol = "6"
    source   = local.gateway_ingress_cidr

    tcp_options {
      min = 443
      max = 443
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_subnet" "public" {
  cidr_block        = var.public_subnet_cidr
  compartment_id    = var.compartment_ocid
  display_name      = "${local.name_prefix}-public-subnet"
  dns_label         = "public"
  route_table_id    = oci_core_route_table.public.id
  security_list_ids = [oci_core_security_list.public.id]
  vcn_id            = oci_core_vcn.optimizer.id
}

resource "oci_artifacts_container_repository" "functions" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}/functions"
  is_public      = false
}

resource "oci_kms_vault" "optimizer" {
  count          = var.create_vault ? 1 : 0
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-vault"
  vault_type     = var.vault_type
}

resource "oci_kms_key" "optimizer" {
  count               = var.create_vault ? 1 : 0
  compartment_id      = var.compartment_ocid
  display_name        = "${local.name_prefix}-secrets-key"
  management_endpoint = oci_kms_vault.optimizer[0].management_endpoint

  key_shape {
    algorithm = "AES"
    length    = 32
  }
}

resource "oci_vault_secret" "openai_api_key" {
  count          = var.create_vault && var.openai_api_key_secret_content_base64 != "" ? 1 : 0
  compartment_id = var.compartment_ocid
  secret_name    = "${local.name_prefix}-openai-api-key"
  vault_id       = oci_kms_vault.optimizer[0].id
  key_id         = oci_kms_key.optimizer[0].id

  secret_content {
    content_type = "BASE64"
    content      = var.openai_api_key_secret_content_base64
  }
}

resource "oci_vault_secret" "database_password" {
  count          = var.create_vault && var.database_password_secret_content_base64 != "" ? 1 : 0
  compartment_id = var.compartment_ocid
  secret_name    = "${local.name_prefix}-database-password"
  vault_id       = oci_kms_vault.optimizer[0].id
  key_id         = oci_kms_key.optimizer[0].id

  secret_content {
    content_type = "BASE64"
    content      = var.database_password_secret_content_base64
  }
}

resource "oci_functions_application" "optimizer" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-functions"
  subnet_ids     = [oci_core_subnet.public.id]

  config = local.function_config
}

resource "oci_functions_function" "cost_retriever" {
  application_id     = oci_functions_application.optimizer.id
  display_name       = "cost-retriever"
  image              = var.cost_retriever_image
  memory_in_mbs      = 512
  timeout_in_seconds = 120

  config = merge(local.function_config, {
    FUNCTION_ROLE = "cost-retriever"
  })
}

resource "oci_functions_function" "resource_manager" {
  application_id     = oci_functions_application.optimizer.id
  display_name       = "resource-manager"
  image              = var.resource_manager_image
  memory_in_mbs      = 512
  timeout_in_seconds = 120

  config = merge(local.function_config, {
    FUNCTION_ROLE            = "resource-manager"
    ENABLE_RESOURCE_MUTATION = tostring(var.enable_resource_mutation)
  })
}

resource "oci_functions_function" "ai_advisor" {
  application_id     = oci_functions_application.optimizer.id
  display_name       = "ai-advisor"
  image              = var.ai_advisor_image
  memory_in_mbs      = 1024
  timeout_in_seconds = 180

  config = merge(local.function_config, {
    FUNCTION_ROLE = "ai-advisor"
  })
}

resource "oci_apigateway_gateway" "optimizer" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-gateway"
  endpoint_type  = var.api_gateway_endpoint_type
  subnet_id      = oci_core_subnet.public.id
}

resource "oci_apigateway_deployment" "optimizer" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-api-v1"
  gateway_id     = oci_apigateway_gateway.optimizer.id
  path_prefix    = "/api/v1"

  specification {
    routes {
      path    = "/health"
      methods = ["GET"]

      backend {
        type        = "ORACLE_FUNCTIONS_BACKEND"
        function_id = oci_functions_function.cost_retriever.id
      }
    }

    routes {
      path    = "/dashboard"
      methods = ["GET"]

      backend {
        type        = "ORACLE_FUNCTIONS_BACKEND"
        function_id = oci_functions_function.cost_retriever.id
      }
    }

    routes {
      path    = "/recommendations"
      methods = ["GET"]

      backend {
        type        = "ORACLE_FUNCTIONS_BACKEND"
        function_id = oci_functions_function.ai_advisor.id
      }
    }

    routes {
      path    = "/copilot"
      methods = ["POST"]

      backend {
        type        = "ORACLE_FUNCTIONS_BACKEND"
        function_id = oci_functions_function.ai_advisor.id
      }
    }

    routes {
      path    = "/resources/actions"
      methods = ["POST"]

      backend {
        type        = "ORACLE_FUNCTIONS_BACKEND"
        function_id = oci_functions_function.resource_manager.id
      }
    }
  }
}

resource "oci_identity_dynamic_group" "functions" {
  compartment_id = var.tenancy_ocid
  name           = local.functions_dynamic_group
  description    = "OCI Cost Optimizer Functions resource principal group."
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.compartment.id = '${var.compartment_ocid}'}"
}

resource "oci_identity_policy" "functions_readonly" {
  compartment_id = var.tenancy_ocid
  name           = "${local.name_prefix}-functions-readonly"
  description    = "Read-only OCI policies for cost optimizer functions."
  statements     = local.readonly_policy_statements
}

resource "oci_identity_policy" "functions_mutation" {
  count          = var.enable_resource_mutation ? 1 : 0
  compartment_id = var.tenancy_ocid
  name           = "${local.name_prefix}-functions-mutation"
  description    = "Optional mutation policies for approved cost optimizer resource actions."
  statements     = local.mutation_policy_statements
}

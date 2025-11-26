terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.110.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
  }
}

provider "azurerm" { 
    features {} 
    use_cli = true
    subscription_id = "1be641d9-96cc-471c-8e67-833a9226badc"
    }

data "azurerm_client_config" "current" {}

variable "db_username" { 
  type = string  
  sensitive = true 
  default = "strava_admin"
}

variable "db_password" { 
  type = string  
  sensitive = true 
  default = "an_overly_complex_password_123*!!!"
} 

variable "secrets" { 
  type = string  
  sensitive = true 
  default = ""
}

variable "home_ip" { 
  type = string  
  sensitive = false 
  default = "0.0.0.0"
}

output "function_app_name" {
  value = azurerm_linux_function_app.func.name
}

resource "random_integer" "suffix" {
  min = 10000000
  max = 99999999
}


resource "azurerm_resource_group" "strava_rg"{
    name = "strava_resources"
    location = "westeurope"
}



resource "azurerm_mssql_firewall_rule" "home" {
  name             = "allow-home"
  server_id        = azurerm_mssql_server.sql_server.id
  start_ip_address = var.home_ip
  end_ip_address   = var.home_ip
}

resource "azurerm_mssql_server" "sql_server" {
    name = "strava-sql-server"
    location = azurerm_resource_group.strava_rg.location
    resource_group_name = azurerm_resource_group.strava_rg.name
    version = "12.0"
    administrator_login = var.db_username
    administrator_login_password = var.db_password  

}

resource "azurerm_mssql_database" "strava_db" {
    name = "strava-db"
    server_id = azurerm_mssql_server.sql_server.id
    sku_name = "S0"
}

resource "azurerm_mssql_firewall_rule" "azure" {
  name             = "allow-azure"
  server_id        = azurerm_mssql_server.sql_server.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}



# ---------- Service plan ------------


resource "azurerm_service_plan" "strava_plan" {
  name                = "strava-plan"
  resource_group_name = azurerm_resource_group.strava_rg.name
  location            = azurerm_resource_group.strava_rg.location
  os_type             = "Linux"
  sku_name            = "B1"
}

# ---------- The Function ------------
resource "azurerm_linux_function_app" "func" {
  name = "strava-function-app-${random_integer.suffix.result}"
  location = azurerm_resource_group.strava_rg.location
  resource_group_name = azurerm_resource_group.strava_rg.name
  service_plan_id = azurerm_service_plan.strava_plan.id
  storage_account_name = azurerm_storage_account.sa_func.name
  storage_account_access_key = azurerm_storage_account.sa_func.primary_access_key
  site_config {
    application_stack {
      python_version = "3.10"     
    }
  }
  identity { type = "SystemAssigned" }
  app_settings = {
    KEYVAULT_URI = azurerm_key_vault.kv.vault_uri
    RAWDATA_STORAGE_URI = trimsuffix(azurerm_storage_account.sa_data.primary_blob_endpoint, "/")
    RAWDATA_CONTAINER_NAME = azurerm_storage_container.storage_data.name,
    AzureWebJobsStorage = azurerm_storage_account.sa_func.primary_connection_string,
    FUNCTIONS_WORKER_RUNTIME = "python",
    FUNCTIONS_EXTENSION_VERSION  = "~4"
    SQL_DB_SERVER = azurerm_mssql_server.sql_server.fully_qualified_domain_name
    SQL_DB_NAME = azurerm_mssql_database.strava_db.name
    SQL_DB_USER = azurerm_mssql_server.sql_server.administrator_login
    SQL_DB_PASSWORD = azurerm_mssql_server.sql_server.administrator_login_password
    SQL_CONNECTION_STRING = "Driver={ODBC Driver 17 for SQL Server};Server=tcp:${azurerm_mssql_server.sql_server.fully_qualified_domain_name},1433;Database=${azurerm_mssql_database.strava_db.name};Uid=${azurerm_mssql_server.sql_server.administrator_login};Pwd=${azurerm_mssql_server.sql_server.administrator_login_password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    WEBSITE_RUN_FROM_PACKAGE = "1"
  }
}

# ---------- Storage for Functions ----------
resource "azurerm_storage_account" "sa_func" {
  name                     = "stravafunc"
  resource_group_name      = azurerm_resource_group.strava_rg.name
  location                 = azurerm_resource_group.strava_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}
# A container for your activities/raw files
# resource "azurerm_storage_container" "storage_func" {
#   name                  = "activities"
#   container_access_type = "private"
#   storage_account_id = azurerm_storage_account.sa_func.id
# }

# ---------- Storage for data ----------
resource "azurerm_storage_account" "sa_data" {
  name                     = "stravadata"
  resource_group_name      = azurerm_resource_group.strava_rg.name
  location                 = azurerm_resource_group.strava_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

# A container for activities/raw files
resource "azurerm_storage_container" "storage_data" {
  name                  = "activities-bronze"
  storage_account_id = azurerm_storage_account.sa_data.id
}

data "azurerm_role_definition" "blob_data_contributor" {
  name  = "Storage Blob Data Contributor"
  scope = azurerm_storage_account.sa_data.id
}

resource "azurerm_role_assignment" "func_to_data_storage" {
  scope                = azurerm_storage_account.sa_data.id
  role_definition_id   = data.azurerm_role_definition.blob_data_contributor.role_definition_id
  principal_id         = azurerm_linux_function_app.func.identity[0].principal_id
}






resource "azurerm_key_vault" "kv" {
    name = "strava-auth-kv"
    resource_group_name = azurerm_resource_group.strava_rg.name
    tenant_id = data.azurerm_client_config.current.tenant_id
    location = azurerm_resource_group.strava_rg.location
    sku_name = "standard"
    rbac_authorization_enabled = true
    
}

resource "azurerm_key_vault_secret" "secrets" {
  name         = "secrets"
  value        = var.secrets
  key_vault_id = azurerm_key_vault.kv.id
  depends_on = [ azurerm_role_assignment.kv_secrets_officer ]
}

resource "azurerm_role_assignment" "kv_secrets_officer" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "func_to_kv_access" {
    scope = azurerm_key_vault.kv.id
    role_definition_name = "Key Vault Secrets Officer"
    principal_id = azurerm_linux_function_app.func.identity[0].principal_id

}
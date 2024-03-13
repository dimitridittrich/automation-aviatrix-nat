# ---------------------------------------------------------------------------------------------------------------------
# TERRAGRUNT CONFIGURATION
# Terragrunt is a thin wrapper for Terraform that provides extra tools for working with multiple Terraform modules,
# remote state, and locking: https://github.com/gruntwork-io/terragrunt
# ---------------------------------------------------------------------------------------------------------------------


# Configure Terragrunt to automatically store tfstate files in an Azure blob storage
remote_state {
  backend = "azurerm"
  config = {
    storage_account_name = "xxxxxxxxxxxxxxxxxxx"
    resource_group_name  = "company-name-tower-management-rg"
    container_name       = "xxxxxxxxxxxxxxxxxxxxxxxx"
    subscription_id      = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    key                  = "${get_env("REPO_NAME")}/${path_relative_to_include()}/terraform.tfstate"
  }
  generate = {
    path      = "backend.g.tf"
    if_exists = "overwrite_terragrunt"
  }
}

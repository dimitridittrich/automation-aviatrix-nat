locals {
  environment_vars = yamldecode(file(find_in_parent_folders("environment.yaml")))
  network_vars = yamldecode(file(find_in_parent_folders("network.yaml")))
  location_vars = yamldecode(file(find_in_parent_folders("regional.yaml")))
  gateway_name = local.network_vars.gateway_name
  location = local.location_vars.location.code
}

terraform {
  source = "../../../../../../../terraform-module/"
  after_hook "plan-nat" {
    commands = ["plan"]
    execute = ["bash","-c","python3 ${get_terragrunt_dir()}/../../../../../../../terraform-module/scripts/avx-nat-plan.py ${local.gateway_name} ${get_terragrunt_dir()} ${local.environment_vars.environment.name} ${local.location}"]
  }
}

include {
  path = find_in_parent_folders()
}

inputs = {
  gateway_name = local.gateway_name
  environment = local.environment_vars.environment.name
  inputs_path = "${get_terragrunt_dir()}"
  location = local.location
}
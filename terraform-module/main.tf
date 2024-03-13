resource "null_resource" "main" {
  triggers = {
    build_number = timestamp()
  }
  provisioner "local-exec" {
    command = "python3 ./scripts/avx-nat.py ${var.gateway_name} ${var.inputs_path} ${var.environment} ${var.location}"
  }
}
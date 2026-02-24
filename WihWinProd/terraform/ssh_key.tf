resource "aws_key_pair" "wihwin" {
  key_name   = "${var.project_name}-${var.environment}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))

  tags = {
    Name = "${var.project_name}-${var.environment}-key"
  }
}

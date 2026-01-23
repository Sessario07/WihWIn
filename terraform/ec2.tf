resource "aws_instance" "wihwin" {
  ami                    = data.aws_ami.amazon_linux_2023_arm.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.wihwin.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    aws_region    = var.aws_region
    account_id    = data.aws_caller_identity.current.account_id
    github_repo   = var.github_repo_url
    github_branch = var.github_branch
    project_name  = var.project_name
  }))

  tags = {
    Name = "${var.project_name}-${var.environment}-ec2"
  }

  lifecycle {
    create_before_destroy = true
  }
}

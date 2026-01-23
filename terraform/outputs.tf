output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.wihwin.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.wihwin.public_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.wihwin.public_dns
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.wihwin.id
}

output "iam_role_arn" {
  description = "IAM role ARN for EC2 instance"
  value       = aws_iam_role.ec2_role.arn
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i <your-key.pem> ec2-user@${aws_instance.wihwin.public_ip}"
}

output "deploy_command" {
  description = "Command to trigger deployment on EC2"
  value       = "ssh -i <your-key.pem> ec2-user@${aws_instance.wihwin.public_ip} 'sudo /opt/${var.project_name}/deploy.sh'"
}

output "application_url" {
  description = "Application URL"
  value       = "http://${aws_instance.wihwin.public_ip}"
}

output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = { for k, v in aws_ecr_repository.app : k => v.repository_url }
}

output "ecr_registry" {
  description = "ECR registry URL"
  value       = split("/", aws_ecr_repository.app["wihwin-fastapi"].repository_url)[0]
}

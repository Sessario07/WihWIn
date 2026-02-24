variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "wihwin"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "c6g.xlarge"
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed for SSH access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key file to attach to EC2"
  type        = string
  default     = "~/.ssh/wihwin-key.pub"
}

variable "budget_limit_amount" {
  description = "Monthly budget limit in USD"
  type        = string
  default     = "30"
}

variable "budget_alert_email" {
  description = "Email address for budget alerts"
  type        = string
}

variable "infra_repo_url" {
  description = "GitHub URL for the WihWinProd infrastructure repository"
  type        = string
  default     = ""
}

variable "infra_repo_branch" {
  description = "Branch to clone from the infra repository"
  type        = string
  default     = "main"
}
